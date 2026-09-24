# -*- coding: utf-8 -*-
import json
import queue
import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView


PROTOCOL_DIRECTIVE = """[DIRECTRIZ SISTEMA - PROTOCOLO CASA DE COMANDO]

Actuará como el Cerebro Central de Procesamiento de la Casa de Comando. Interactuará con el usuario y con 6 bots internos (Cari, Cami, Chie, Sunna, Chloe, Scarlet).

REGLAS DE PROTOCOLO DE MENSAJES:
1. Recepción de Ticket: Cuando un bot envíe un mensaje, usará el formato:
   ({BOT_NAME}) codigo {ID} #{ACCION} [@USER] [CANAL: {canal}] "{mensaje}"

2. Formato de Respuesta Obligatorio: Su respuesta DEBE iniciar citando al bot y su código de ticket:
   respuesta a ({BOT_NAME} {ID}) "{tu_respuesta}"

3. Control de Estado y Cierre:
   - Mantenga el contexto del ticket activo ({ID}) hasta que el bot envíe el mensaje de cierre:
     ({BOT_NAME}) codigo {ID} #resuelto
   - Al recibir dicho cierre, usted debe responder obligatoriamente:
     ({BOT_NAME} {ID}) #terminado

4. Múltiples Contextos: Si recibe preguntas generales del usuario fuera del protocolo de tickets, responda de forma natural sin incluir códigos.
"""


# Se ejecuta dentro del navegador. No usa polling continuo:
# MutationObserver reacciona a cambios del DOM y un debounce determina
# cuándo la respuesta ha dejado de cambiar.
WEB_MONITOR_JS = r"""
(() => {
    if (
        window.__casaComandoWebQueue &&
        window.__casaComandoWebQueue.installed
    ) {
        return "ALREADY_INSTALLED";
    }

    const state = {
        installed: true,
        waitingForResponse: false,
        stopSeen: false,
        baselineText: "",
        firstMutationAt: 0,
        sendClickedAt: 0,
        settleTimer: null,
        bridge: null,
        sequence: 0,
        operationId: 0,
        activeTicketId: "",
    };

    const sendBridgeEvent = (eventType, payload) => {
        try {
            if (
                state.bridge &&
                typeof state.bridge.report === "function"
            ) {
                state.bridge.report(
                    eventType,
                    String(payload ?? "")
                );
            }
        } catch (error) {
            console.debug(
                "[CASA_COMANDO_WEB_QUEUE]",
                "bridge error",
                String(error)
            );
        }
    };

    const findButtonByLabels = (labels) => {
        const candidates = document.querySelectorAll("button");

        for (const button of candidates) {
            const label = (
                button.getAttribute("aria-label") ||
                button.getAttribute("title") ||
                button.textContent ||
                ""
            ).trim().toLowerCase();

            if (labels.some((value) => label.includes(value))) {
                return button;
            }
        }

        return null;
    };

    const findStopButton = () => {
        return findButtonByLabels([
            "stop",
            "detener",
            "stop generating",
            "detener generación",
            "detener la generación",
            "stop response",
            "cancel response",
        ]);
    };

    const findSendButton = () => {
        return findButtonByLabels([
            "send",
            "enviar",
            "send message",
            "enviar mensaje",
        ]);
    };

    const extractLatestAssistantText = () => {
        const selectors = [
            '[data-message-author-role="assistant"]',
            '[data-role="assistant"]',
            '[data-testid*="assistant"]',
            '[class*="assistant"]',
            "message-content",
            ".markdown",
            ".prose",
        ];

        const values = [];

        for (const selector of selectors) {
            try {
                const nodes = document.querySelectorAll(selector);

                for (const node of nodes) {
                    const value = (
                        node.innerText ||
                        node.textContent ||
                        ""
                    ).trim();

                    if (value) {
                        values.push(value);
                    }
                }
            } catch (_) {
                // Un selector incompatible no debe romper el observer.
            }
        }

        if (values.length > 0) {
            return values[values.length - 1];
        }

        return (document.body?.innerText || "").trim();
    };

    const completeIfStable = () => {
        if (!state.waitingForResponse) {
            return;
        }

        if (!state.sendClickedAt) {
            return;
        }

        const stopButton = findStopButton();

        if (stopButton) {
            state.stopSeen = true;
            return;
        }

        const now = Date.now();
        const minimumSettleMs = 1200;

        if (
            now - state.sendClickedAt < minimumSettleMs ||
            (
                state.firstMutationAt &&
                now - state.firstMutationAt < minimumSettleMs
            )
        ) {
            if (state.settleTimer !== null) {
                clearTimeout(state.settleTimer);
            }

            state.settleTimer = setTimeout(
                completeIfStable,
                minimumSettleMs
            );
            return;
        }

        const assistantText = extractLatestAssistantText();
        const bodyText = (
            document.body?.innerText || ""
        ).trim();

        if (!assistantText && !bodyText) {
            return;
        }

        const payload = JSON.stringify({
            ticket_id: state.activeTicketId,
            sequence: state.sequence,
            operation_id: state.operationId,
            text: assistantText || bodyText,
        });

        state.waitingForResponse = false;
        state.stopSeen = false;
        state.firstMutationAt = 0;
        state.sendClickedAt = 0;

        sendBridgeEvent(
            "RESPONSE_COMPLETE",
            payload
        );
    };

    const scheduleCompletionCheck = () => {
        if (
            !state.waitingForResponse ||
            !state.sendClickedAt
        ) {
            return;
        }

        if (!state.firstMutationAt) {
            state.firstMutationAt = Date.now();
        }

        if (state.settleTimer !== null) {
            clearTimeout(state.settleTimer);
        }

        state.settleTimer = setTimeout(
            completeIfStable,
            1200
        );
    };

    window.__casaComandoWebQueue = {
        installed: true,

        beginSend(ticketId, operationId) {
            state.sequence += 1;
            state.operationId = Number(operationId) || (state.operationId + 1);
            state.activeTicketId =
                String(ticketId ?? "");
            state.waitingForResponse = true;
            state.stopSeen = Boolean(findStopButton());
            state.baselineText = (
                document.body?.innerText || ""
            ).trim();
            state.firstMutationAt = 0;
            state.sendClickedAt = 0;

            if (state.settleTimer !== null) {
                clearTimeout(state.settleTimer);
                state.settleTimer = null;
            }
        },

        markSendClicked() {
            state.sendClickedAt = Date.now();
            state.firstMutationAt =
                state.sendClickedAt;
            scheduleCompletionCheck();
        },

        setActiveTicket(ticketId) {
            state.activeTicketId =
                String(ticketId ?? "");
        },

        setOperation(operationId) {
            state.operationId = Number(operationId) || (state.operationId + 1);
        },

        cancelOperation() {
            state.operationId += 1;
            state.waitingForResponse = false;
            state.activeTicketId = "";
            if (state.settleTimer !== null) {
                clearTimeout(state.settleTimer);
                state.settleTimer = null;
            }
        },

        getState() {
            return JSON.stringify({
                sequence: state.sequence,
                operation_id: state.operationId,
                ticket_id: state.activeTicketId,
                waiting: state.waitingForResponse,
            });
        },
    };

    const installObserver = () => {
        const root =
            document.body ||
            document.documentElement;

        if (!root) {
            sendBridgeEvent(
                "MONITOR_ERROR",
                "NO_DOM_ROOT"
            );
            return;
        }

        const observer = new MutationObserver(
            (mutations) => {
                if (
                    !state.waitingForResponse ||
                    mutations.length === 0
                ) {
                    return;
                }

                if (findStopButton()) {
                    state.stopSeen = true;
                }

                scheduleCompletionCheck();
            }
        );

        observer.observe(
            root,
            {
                subtree: true,
                childList: true,
                characterData: true,
            }
        );

        state.observer = observer;

        sendBridgeEvent(
            "MONITOR_READY",
            "MutationObserver instalado"
        );
    };

    const connectQtWebChannel = () => {
        if (
            typeof qt === "undefined" ||
            !qt.webChannelTransport
        ) {
            sendBridgeEvent(
                "MONITOR_ERROR",
                "QT_WEBCHANNEL_TRANSPORT_UNAVAILABLE"
            );
            return;
        }

        try {
            new QWebChannel(
                qt.webChannelTransport,
                (channel) => {
                    state.bridge =
                        channel.objects.casaQueueBridge;

                    installObserver();
                }
            );
        } catch (error) {
            sendBridgeEvent(
                "MONITOR_ERROR",
                String(error)
            );
        }
    };

    const existingScript = document.querySelector(
        'script[data-casa-comando-webchannel="true"]'
    );

    if (existingScript) {
        connectQtWebChannel();
    } else {
        const script = document.createElement("script");
        script.src =
            "qrc:///qtwebchannel/qwebchannel.js";
        script.dataset.casaComandoWebchannel =
            "true";
        script.onload = connectQtWebChannel;
        script.onerror = () => {
            sendBridgeEvent(
                "MONITOR_ERROR",
                "QWEBCHANNEL_JS_LOAD_FAILED"
            );
        };

        (
            document.head ||
            document.documentElement
        ).appendChild(script);
    }

    return "INSTALL_REQUESTED";
})();
"""


@dataclass
class BotTicket:
    ticket_id: str
    bot_name: str
    action: str
    user: str
    channel: str
    message: str
    status: str = "PENDING"


class _WebQueueBridge(QObject):
    event_received = Signal(str, str)

    @Slot(str, str)
    def report(
        self,
        event_type: str,
        payload: str,
    ) -> None:
        self.event_received.emit(
            event_type,
            payload,
        )


class _QueueWorker(QObject):
    """Estado FIFO y temporización ejecutados en QThread."""

    ticket_started = Signal(object)
    web_action_requested = Signal(str, str, str)
    ticket_failed = Signal(object, str)
    ticket_finished = Signal(object)
    busy_changed = Signal(bool)
    queue_error = Signal(str, str)
    stopped = Signal()

    def __init__(
        self,
        timeout_ms: int,
        circuit_threshold: int,
        circuit_cooldown_ms: int,
    ) -> None:
        super().__init__()

        self.timeout_ms = timeout_ms
        self.circuit_threshold = circuit_threshold
        self.circuit_cooldown_ms = circuit_cooldown_ms

        self.msg_queue: queue.Queue[BotTicket] = (
            queue.Queue()
        )
        self.current_ticket: BotTicket | None = None

        self.is_busy = False
        self.awaiting_terminated = False
        self.close_in_flight = False

        self.consecutive_failures = 0
        self.circuit_open = False

        self._timeout_timer: QTimer | None = None
        self._circuit_timer: QTimer | None = None
        self._running = True
        self._queued_ids: set[str] = set()

    @Slot()
    def start(self) -> None:
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(
            self._on_timeout
        )

        self._circuit_timer = QTimer(self)
        self._circuit_timer.setSingleShot(True)
        self._circuit_timer.timeout.connect(
            self._half_open_circuit
        )

        self._process_next()

    @Slot(object)
    def enqueue(self, ticket: BotTicket) -> None:
        if not self._running:
            self.queue_error.emit(
                ticket.ticket_id,
                "QUEUE_STOPPED",
            )
            return

        if ticket.ticket_id in self._queued_ids:
            self.queue_error.emit(
                ticket.ticket_id,
                "DUPLICATE_TICKET_ID",
            )
            return

        if (
            self.current_ticket is not None and
            self.current_ticket.ticket_id ==
            ticket.ticket_id
        ):
            self.queue_error.emit(
                ticket.ticket_id,
                "DUPLICATE_ACTIVE_TICKET_ID",
            )
            return

        self.msg_queue.put(ticket)
        self._queued_ids.add(ticket.ticket_id)
        self._process_next()

    @Slot()
    def process_next(self) -> None:
        self._process_next()

    @Slot()
    def request_close(self) -> None:
        ticket = self.current_ticket

        if ticket is None:
            return

        if (
            self.awaiting_terminated or
            self.close_in_flight
        ):
            return

        self.close_in_flight = True

        prompt = (
            f"({ticket.bot_name}) "
            f"codigo {ticket.ticket_id} "
            f"#resuelto"
        )

        self.web_action_requested.emit(
            "close",
            ticket.ticket_id,
            prompt,
        )

    @Slot(str, str, bool, str)
    def injection_result(
        self,
        ticket_id: str,
        action_kind: str,
        success: bool,
        detail: str,
    ) -> None:
        ticket = self.current_ticket

        if ticket is None:
            return

        if ticket.ticket_id != ticket_id:
            return

        if action_kind == "close":
            self.close_in_flight = False

            if not success:
                self._fail_current(
                    detail or "CLOSE_INJECTION_FAILED"
                )
                return

            self.awaiting_terminated = True
            return

        if action_kind == "ticket":
            if not success:
                self._fail_current(
                    detail or "TICKET_INJECTION_FAILED"
                )

    @Slot(str)
    def response_observed(
        self,
        response_text: str,
    ) -> None:
        if (
            self.current_ticket is not None and
            response_text.strip()
        ):
            self.consecutive_failures = 0

    @Slot(str)
    def terminated_received(
        self,
        ticket_id: str,
    ) -> None:
        ticket = self.current_ticket

        if (
            ticket is None or
            ticket.ticket_id != ticket_id or
            not self.awaiting_terminated
        ):
            return

        self.awaiting_terminated = False
        self._finish_current()

    @Slot()
    def external_failure(self) -> None:
        if self.current_ticket is not None:
            self._fail_current(
                "WEB_HEALTH_FAILURE"
            )
        else:
            self._record_failure(
                "WEB_HEALTH_FAILURE"
            )

    @Slot()
    def stop(self) -> None:
        self._running = False

        if self._timeout_timer is not None:
            self._timeout_timer.stop()

        if self._circuit_timer is not None:
            self._circuit_timer.stop()

        self.stopped.emit()

    def _process_next(self) -> None:
        if (
            not self._running or
            self.is_busy or
            self.circuit_open or
            self.msg_queue.empty()
        ):
            return

        ticket = self.msg_queue.get()
        self._queued_ids.discard(
            ticket.ticket_id
        )

        ticket.status = "PROCESSING"
        self.current_ticket = ticket
        self.is_busy = True
        self.awaiting_terminated = False
        self.close_in_flight = False

        if self._timeout_timer is not None:
            self._timeout_timer.start(
                self.timeout_ms
            )

        self.busy_changed.emit(True)
        self.ticket_started.emit(ticket)

        prompt = (
            f"({ticket.bot_name}) codigo "
            f"{ticket.ticket_id} #{ticket.action} "
            f"[{ticket.user}] [{ticket.channel}] "
            f'"{ticket.message}"'
        )

        self.web_action_requested.emit(
            "ticket",
            ticket.ticket_id,
            prompt,
        )

    def _on_timeout(self) -> None:
        if self.current_ticket is None:
            return

        self._fail_current(
            f"TIMEOUT_{self.timeout_ms // 1000}s"
        )

    def _fail_current(
        self,
        reason: str,
    ) -> None:
        ticket = self.current_ticket

        if ticket is None:
            return

        ticket.status = "FAILED"

        if self._timeout_timer is not None:
            self._timeout_timer.stop()

        self.current_ticket = None
        self.is_busy = False
        self.awaiting_terminated = False
        self.close_in_flight = False

        self.ticket_failed.emit(
            ticket,
            reason,
        )
        self.busy_changed.emit(False)

        self._record_failure(reason)

        if (
            self._running and
            not self.circuit_open
        ):
            self._process_next()

    def _finish_current(self) -> None:
        ticket = self.current_ticket

        if ticket is None:
            return

        ticket.status = "RESOLVED"

        if self._timeout_timer is not None:
            self._timeout_timer.stop()

        self.current_ticket = None
        self.is_busy = False
        self.awaiting_terminated = False
        self.close_in_flight = False
        self.consecutive_failures = 0

        self.ticket_finished.emit(ticket)
        self.busy_changed.emit(False)

        QTimer.singleShot(
            100,
            self._process_next,
        )

    def _record_failure(
        self,
        reason: str,
    ) -> None:
        self.consecutive_failures += 1

        if (
            self.consecutive_failures <
            self.circuit_threshold
        ):
            return

        if self.circuit_open:
            return

        self.circuit_open = True

        self.queue_error.emit(
            "__circuit__",
            f"CIRCUIT_OPEN: {reason}",
        )

        if self._circuit_timer is not None:
            self._circuit_timer.start(
                self.circuit_cooldown_ms
            )

    @Slot()
    def _half_open_circuit(self) -> None:
        if not self._running:
            return

        self.circuit_open = False
        self.consecutive_failures = 0

        self.queue_error.emit(
            "__circuit__",
            "CIRCUIT_HALF_OPEN: reintentando cola",
        )

        self._process_next()


class WebChatQueueManager(QObject):
    """
    Gestor FIFO anti-deadlock para SUPER CHAT.

    La cola y sus timers se ejecutan en QThread.
    QWebEngineView se manipula exclusivamente desde GUI/Qt.
    """

    ticket_processed = Signal(str, str)
    ticket_started = Signal(str, str)
    ticket_finished = Signal(str, str)
    ticket_failed = Signal(str, str)
    queue_error = Signal(str, str)

    enqueue_requested = Signal(object)
    process_requested = Signal()
    close_requested = Signal()
    stop_requested = Signal()

    injection_result_requested = Signal(
        str,
        str,
        bool,
        str,
    )
    response_observed_requested = Signal(str)
    terminated_requested = Signal(str)
    health_failure_requested = Signal()

    def __init__(
        self,
        web_view: QWebEngineView,
        parent: QObject | None = None,
        timeout_seconds: int = 45,
        circuit_threshold: int = 3,
        circuit_cooldown_seconds: int = 10,
    ) -> None:
        super().__init__(parent)

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds debe ser > 0"
            )

        if circuit_threshold <= 0:
            raise ValueError(
                "circuit_threshold debe ser > 0"
            )

        if circuit_cooldown_seconds <= 0:
            raise ValueError(
                "circuit_cooldown_seconds debe ser > 0"
            )

        self.web_view = web_view
        self.current_ticket: BotTicket | None = None
        self.is_busy = False
        self.protocol_initialized = False
        self.monitor_initialized = False

        self._protocol_pending = False
        self._shutdown_started = False
        self._web_operation_id = 0

        self._protocol_send_timer = QTimer(self)
        self._protocol_send_timer.setSingleShot(True)
        self._protocol_send_timer.timeout.connect(
            self._on_protocol_send_timeout
        )

        self._response_pattern = self._safe_compile(
            r'respuesta\s+a\s*\(\s*'
            r'(?P<bot>[^()\n]+?)\s+'
            r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)'
            r'\s*[“"](?P<text>.*?)[”"]',
            re.IGNORECASE | re.DOTALL,
        )

        self._terminated_pattern = self._safe_compile(
            r'\(\s*(?P<bot>[^()\n]+?)\s+'
            r'(?P<ticket>[A-Za-z0-9_.:-]+)\s*\)'
            r'\s+#terminado\b',
            re.IGNORECASE,
        )

        if (
            self._response_pattern is None or
            self._terminated_pattern is None
        ):
            raise RuntimeError(
                "No se pudieron compilar "
                "las expresiones del protocolo"
            )

        self._thread = QThread(self)
        self._worker = _QueueWorker(
            timeout_ms=timeout_seconds * 1000,
            circuit_threshold=circuit_threshold,
            circuit_cooldown_ms=(
                circuit_cooldown_seconds * 1000
            ),
        )
        self._worker.moveToThread(
            self._thread
        )

        # La cola expuesta es la FIFO real del worker.
        self.msg_queue = self._worker.msg_queue

        self.enqueue_requested.connect(
            self._worker.enqueue
        )
        self.process_requested.connect(
            self._worker.process_next
        )
        self.close_requested.connect(
            self._worker.request_close
        )
        self.stop_requested.connect(
            self._worker.stop
        )
        self.injection_result_requested.connect(
            self._worker.injection_result
        )
        self.response_observed_requested.connect(
            self._worker.response_observed
        )
        self.terminated_requested.connect(
            self._worker.terminated_received
        )
        self.health_failure_requested.connect(
            self._worker.external_failure
        )

        self._worker.ticket_started.connect(
            self._on_worker_ticket_started
        )
        self._worker.web_action_requested.connect(
            self._on_web_action_requested
        )
        self._worker.ticket_failed.connect(
            self._on_worker_ticket_failed
        )
        self._worker.ticket_finished.connect(
            self._on_worker_ticket_finished
        )
        self._worker.busy_changed.connect(
            self._on_worker_busy_changed
        )
        self._worker.queue_error.connect(
            self._on_worker_queue_error
        )
        self._worker.stopped.connect(
            self._thread.quit
        )

        self._thread.started.connect(
            self._worker.start
        )
        self._thread.finished.connect(
            self._worker.deleteLater
        )

        self._bridge = _WebQueueBridge()

        # Qt permite un solo QWebChannel por página. Si la GUI ya
        # tiene uno, lo reutilizamos para no romper otros bridges.
        existing_channel = self.web_view.page().webChannel()

        if existing_channel is not None:
            self._channel = existing_channel
        else:
            self._channel = QWebChannel(
                self.web_view.page()
            )
            self.web_view.page().setWebChannel(
                self._channel
            )

        self._channel.registerObject(
            "casaQueueBridge",
            self._bridge,
        )

        self._bridge.event_received.connect(
            self._on_web_bridge_event
        )
        self.web_view.loadFinished.connect(
            self._on_page_loaded
        )

        self._thread.start()

    # ------------------------------------------------------------------
    # API PÚBLICA
    # ------------------------------------------------------------------

    def initialize_protocol(self) -> None:
        """Instala el monitor DOM y envía las directrices una vez."""
        if (
            self.protocol_initialized or
            self._protocol_pending
        ):
            return

        self._protocol_pending = True
        self._install_web_monitor()

    def enqueue_bot_message(
        self,
        bot_name: str,
        ticket_id: str,
        action: str,
        message: str,
        user: str = "@usuario",
        channel: str = "/general",
    ) -> None:
        if not bot_name.strip():
            raise ValueError(
                "bot_name no puede estar vacío"
            )

        if not ticket_id.strip():
            raise ValueError(
                "ticket_id no puede estar vacío"
            )

        if not action.strip():
            raise ValueError(
                "action no puede estar vacío"
            )

        if not message.strip():
            raise ValueError(
                "message no puede estar vacío"
            )

        ticket = BotTicket(
            ticket_id=ticket_id.strip(),
            bot_name=bot_name.strip(),
            action=action.strip(),
            user=user.strip() or "@usuario",
            channel=channel.strip() or "/general",
            message=message.strip(),
        )

        self.enqueue_requested.emit(ticket)

    def process_next(self) -> None:
        """Pide al QThread que reevalúe la cola sin tocarla directamente."""
        if not self.is_busy:
            self.process_requested.emit()

    def close_current_ticket(self) -> None:
        self.close_requested.emit()

    def register_ticket_response(
        self,
        response_text: str,
    ) -> bool:
        return self._consume_response(
            response_text
        )

    def shutdown(self) -> None:
        """Detiene worker y QThread sin dejar temporizadores activos."""
        if self._shutdown_started:
            return

        self._shutdown_started = True
        self._cancel_web_operation()
        self.stop_requested.emit()
        self._thread.wait(2000)

        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

    # ------------------------------------------------------------------
    # WEB / DOM / QWEBCHANNEL
    # ------------------------------------------------------------------

    @Slot(bool)
    def _on_page_loaded(self, ok: bool) -> None:
        if not ok:
            self.queue_error.emit(
                "__web__",
                "PAGE_LOAD_FAILED",
            )
            self.health_failure_requested.emit()
            return

        self.monitor_initialized = False

        if (
            not self.protocol_initialized and
            not self._protocol_pending
        ):
            self._protocol_pending = True

        self._install_web_monitor()

    def _install_web_monitor(self) -> None:
        if self._shutdown_started:
            return

        self.web_view.page().runJavaScript(
            WEB_MONITOR_JS,
            self._on_monitor_install_result,
        )

    @Slot()
    def _on_protocol_send_timeout(self) -> None:
        if self.protocol_initialized:
            return

        self._protocol_pending = True
        self.queue_error.emit(
            "__protocol__",
            "PROTOCOL_SEND_TIMEOUT",
        )
        self.health_failure_requested.emit()

    def _on_monitor_install_result(
        self,
        result: Any,
    ) -> None:
        if result == "ALREADY_INSTALLED":
            self.monitor_initialized = True

            if (
                self._protocol_pending and
                not self.protocol_initialized
            ):
                self._send_protocol_directive()

            return

        if result == "INSTALL_REQUESTED":
            return

        if result:
            self.queue_error.emit(
                "__monitor__",
                str(result),
            )

    @Slot(str, str)
    def _on_web_bridge_event(
        self,
        event_type: str,
        payload: str,
    ) -> None:
        if event_type == "MONITOR_READY":
            self.monitor_initialized = True

            if (
                self._protocol_pending and
                not self.protocol_initialized
            ):
                self._send_protocol_directive()

            return

        if event_type == "SEND_OK":
            try:
                send_event = json.loads(payload)
            except (TypeError, ValueError):
                send_event = {}

            sent_ticket_id = str(
                send_event.get("ticket_id", "")
            )

            if sent_ticket_id == "__protocol__":
                if self._protocol_send_timer.isActive():
                    self._protocol_send_timer.stop()

                self.protocol_initialized = True

            return

        if event_type == "RESPONSE_COMPLETE":
            try:
                event = json.loads(payload)
            except (TypeError, ValueError):
                event = {
                    "ticket_id": "",
                    "text": payload,
                }

            ticket_id = str(
                event.get("ticket_id", "")
            )
            operation_id = int(
                event.get("operation_id", 0) or 0
            )
            text = str(
                event.get("text", "")
            )

            if (
                operation_id and
                operation_id != self._web_operation_id
            ):
                return

            if not text.strip():
                return

            if (
                self.current_ticket is not None and
                ticket_id and
                ticket_id !=
                self.current_ticket.ticket_id
            ):
                # Respuesta tardía de un ticket anterior.
                return

            self._consume_response(
                text,
                expected_ticket_id=ticket_id,
            )
            return

        if event_type in {
            "MONITOR_ERROR",
            "SEND_ERROR",
        }:
            self.monitor_initialized = False

            error_ticket_id = ""
            error_payload = payload

            if event_type == "SEND_ERROR":
                try:
                    error_event = json.loads(payload)
                except (TypeError, ValueError):
                    error_event = {}

                error_ticket_id = str(
                    error_event.get("ticket_id", "")
                )
                error_payload = str(
                    error_event.get(
                        "error",
                        payload,
                    )
                )

                if (
                    error_ticket_id and
                    self.current_ticket is not None and
                    error_ticket_id !=
                    self.current_ticket.ticket_id
                ):
                    return

            self.queue_error.emit(
                error_ticket_id or "__monitor__",
                error_payload,
            )
            self.health_failure_requested.emit()

    def _send_protocol_directive(self) -> None:
        self._protocol_pending = False

        if self._protocol_send_timer.isActive():
            self._protocol_send_timer.stop()

        self._protocol_send_timer.start(5000)

        self._inject_to_browser(
            PROTOCOL_DIRECTIVE,
            action_kind="protocol",
            ticket_id="__protocol__",
            send=True,
        )

    def _on_web_action_requested(
        self,
        action_kind: str,
        ticket_id: str,
        prompt: str,
    ) -> None:
        self._inject_to_browser(
            prompt,
            action_kind=action_kind,
            ticket_id=ticket_id,
            send=True,
            mark_send=(
                action_kind in {"ticket", "close"}
            ),
        )

    def _inject_to_browser(
        self,
        text: str,
        action_kind: str,
        ticket_id: str,
        send: bool = True,
        mark_send: bool = False,
    ) -> None:
        js_text = json.dumps(
            text,
            ensure_ascii=False,
        )
        js_ticket_id = json.dumps(
            ticket_id,
            ensure_ascii=False,
        )

        self._web_operation_id += 1
        operation_id = self._web_operation_id
        js_operation_id = str(operation_id)

        send_code = """
            (() => {
                const operationId = %OPERATION_ID%;
                setTimeout(() => {
                    if (
                        !window.__casaComandoWebQueue ||
                        typeof window.__casaComandoWebQueue.getState !== "function"
                    ) {
                        return;
                    }

                    const currentState = JSON.parse(
                        window.__casaComandoWebQueue.getState()
                    );

                    if (Number(currentState.operation_id) !== operationId) {
                        return;
                    }

                    const buttons = Array.from(
                        document.querySelectorAll("button")
                    );

                    const button = buttons.find(
                        (candidate) => {
                            const label = (
                                candidate.getAttribute(
                                    "aria-label"
                                ) ||
                                candidate.getAttribute(
                                    "title"
                                ) ||
                                candidate.textContent ||
                                ""
                            ).trim().toLowerCase();

                            return (
                                label === "send" ||
                                label === "enviar" ||
                                label.includes(
                                    "send message"
                                ) ||
                                label.includes(
                                    "enviar mensaje"
                                )
                            );
                        }
                    );

                    if (!button || button.disabled) {
                        sendBridgeEvent(
                            "SEND_ERROR",
                            JSON.stringify({
                                ticket_id:
                                    state.activeTicketId,
                                error:
                                    "SEND_BUTTON_NOT_FOUND"
                            })
                        );
                        return;
                    }

                    button.click();

                    sendBridgeEvent(
                        "SEND_OK",
                        JSON.stringify({
                            ticket_id:
                                state.activeTicketId,
                            operation_id:
                                operationId
                        })
                    );

                    if (
                        window.__casaComandoWebQueue &&
                        typeof window.__casaComandoWebQueue
                            .markSendClicked ===
                            "function"
                    ) {
                        window.__casaComandoWebQueue
                            .markSendClicked();
                    }
                }, 500);
            })();
        """ if send else ""

        set_ticket_code = f"""
            if (
                window.__casaComandoWebQueue &&
                typeof window.__casaComandoWebQueue
                    .setActiveTicket === "function"
            ) {{
                window.__casaComandoWebQueue
                    .setActiveTicket({js_ticket_id});
            }}

            if (
                window.__casaComandoWebQueue &&
                typeof window.__casaComandoWebQueue
                    .setOperation === "function"
            ) {{
                window.__casaComandoWebQueue
                    .setOperation({js_operation_id});
            }}
        """

        begin_send_code = f"""
            if (
                window.__casaComandoWebQueue &&
                typeof window.__casaComandoWebQueue
                    .beginSend === "function"
            ) {{
                window.__casaComandoWebQueue
                    .beginSend({js_ticket_id}, {js_operation_id});
            }}
        """ if mark_send else ""

        js_code = f"""
        (() => {{
            const text = {js_text};

            const inputArea =
                document.querySelector(
                    "textarea, " +
                    "div[contenteditable=\"true\"]"
                );

            if (!inputArea) {{
                return "ERROR: NO_DOM_INPUT";
            }}

            {set_ticket_code}
            {begin_send_code}

            if (
                inputArea.tagName ===
                "TEXTAREA"
            ) {{
                const setter =
                    Object.getOwnPropertyDescriptor(
                        HTMLTextAreaElement.prototype,
                        "value"
                    )?.set;

                if (setter) {{
                    setter.call(
                        inputArea,
                        text
                    );
                }} else {{
                    inputArea.value =
                        text;
                }}

                inputArea.dispatchEvent(
                    new Event(
                        "input",
                        {{ bubbles: true }}
                    )
                );

                inputArea.dispatchEvent(
                    new Event(
                        "change",
                        {{ bubbles: true }}
                    )
                );
            }} else {{
                inputArea.focus();
                inputArea.textContent =
                    text;

                inputArea.dispatchEvent(
                    new InputEvent(
                        "input",
                        {{
                            bubbles: true,
                            inputType: "insertText",
                            data: text
                        }}
                    )
                );
            }}

            {send_code}

            return "OK: INJECTED";
        }})();
        """

        def handle_result(
            result: Any,
        ) -> None:
            result_text = str(
                result or ""
            )

            if action_kind == "protocol":
                if not result_text.startswith(
                    "OK"
                ):
                    self._protocol_pending = True
                    self.queue_error.emit(
                        "__protocol__",
                        result_text,
                    )
                    self.health_failure_requested.emit()
                    return

                self.protocol_initialized = True
                return

            self.injection_result_requested.emit(
                ticket_id,
                action_kind,
                result_text.startswith(
                    "OK"
                ),
                result_text,
            )

        self.web_view.page().runJavaScript(
            js_code,
            handle_result,
        )

    def _cancel_web_operation(self) -> None:
        self._web_operation_id += 1
        try:
            self.web_view.page().runJavaScript(
                """
                if (
                    window.__casaComandoWebQueue &&
                    typeof window.__casaComandoWebQueue.cancelOperation === "function"
                ) {
                    window.__casaComandoWebQueue.cancelOperation();
                }
                """
            )
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # PROTOCOLO
    # ------------------------------------------------------------------

    def _consume_response(
        self,
        raw_text: str,
        expected_ticket_id: str = "",
    ) -> bool:
        ticket = self.current_ticket

        if ticket is None:
            return False

        if (
            expected_ticket_id and
            expected_ticket_id !=
            ticket.ticket_id
        ):
            return False

        text = raw_text.strip()

        if len(text) > self.MAX_RESPONSE_PARSE_CHARS:
            text = text[-self.MAX_RESPONSE_PARSE_CHARS:]

        if not text:
            return False

        if self._extract_terminated(
            text,
            ticket,
        ):
            self.terminated_requested.emit(
                ticket.ticket_id
            )
            self.response_observed_requested.emit(
                text
            )
            self.ticket_processed.emit(
                ticket.ticket_id,
                text,
            )
            return True

        parsed_text = self._extract_response_text(
            text,
            ticket,
        )

        if not parsed_text:
            # Si el encabezado fue alterado, se conserva
            # la evidencia observada antes del timeout.
            parsed_text = text[-12000:]

        self.response_observed_requested.emit(
            parsed_text
        )
        self.ticket_processed.emit(
            ticket.ticket_id,
            parsed_text,
        )
        return True

    MAX_RESPONSE_PARSE_CHARS = 20_000

    def _extract_response_text(
        self,
        raw_text: str,
        ticket: BotTicket,
    ) -> str:
        raw_text = raw_text.strip()
        if not raw_text:
            return ""

        if len(raw_text) > self.MAX_RESPONSE_PARSE_CHARS:
            raw_text = raw_text[-self.MAX_RESPONSE_PARSE_CHARS:]

        pattern = self._response_pattern

        if pattern is None:
            return ""

        matches = list(
            pattern.finditer(raw_text)
        )

        for match in reversed(matches):
            bot = match.group(
                "bot"
            ).strip()
            ticket_id = match.group(
                "ticket"
            ).strip()

            if (
                ticket_id.casefold() ==
                ticket.ticket_id.casefold()
                and
                bot.casefold() ==
                ticket.bot_name.casefold()
            ):
                return match.group(
                    "text"
                ).strip()

        return ""



    def _extract_terminated(
        self,
        raw_text: str,
        ticket: BotTicket,
    ) -> bool:
        pattern = self._terminated_pattern

        if pattern is None:
            return False

        for match in pattern.finditer(
            raw_text
        ):
            bot = match.group(
                "bot"
            ).strip()
            ticket_id = match.group(
                "ticket"
            ).strip()

            if (
                ticket_id.casefold() ==
                ticket.ticket_id.casefold()
                and
                bot.casefold() ==
                ticket.bot_name.casefold()
            ):
                return True

        return False

    @staticmethod
    def _safe_compile(
        pattern: str,
        flags: int = 0,
    ):
        try:
            return re.compile(
                pattern,
                flags,
            )
        except re.error:
            return None

    # ------------------------------------------------------------------
    # SEÑALES DEL WORKER
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_worker_ticket_started(
        self,
        ticket: BotTicket,
    ) -> None:
        self.current_ticket = ticket
        self.is_busy = True

        self.ticket_started.emit(
            ticket.ticket_id,
            ticket.bot_name,
        )

    @Slot(object, str)
    def _on_worker_ticket_failed(
        self,
        ticket: BotTicket,
        reason: str,
    ) -> None:
        self._cancel_web_operation()

        if (
            self.current_ticket is not None and
            self.current_ticket.ticket_id ==
            ticket.ticket_id
        ):
            self.current_ticket = None

        self.is_busy = False

        self.ticket_failed.emit(
            ticket.ticket_id,
            reason,
        )
        self.queue_error.emit(
            ticket.ticket_id,
            reason,
        )

    @Slot(object)
    def _on_worker_ticket_finished(
        self,
        ticket: BotTicket,
    ) -> None:
        if (
            self.current_ticket is not None and
            self.current_ticket.ticket_id ==
            ticket.ticket_id
        ):
            self.current_ticket = None

        self.is_busy = False

        self.ticket_finished.emit(
            ticket.ticket_id,
            ticket.bot_name,
        )

    @Slot(bool)
    def _on_worker_busy_changed(
        self,
        busy: bool,
    ) -> None:
        self.is_busy = busy

    @Slot(str, str)
    def _on_worker_queue_error(
        self,
        ticket_id: str,
        error_text: str,
    ) -> None:
        self.queue_error.emit(
            ticket_id,
            error_text,
        )
