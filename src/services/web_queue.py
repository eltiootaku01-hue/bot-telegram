import json
import queue
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal
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


@dataclass
class BotTicket:
    ticket_id: str
    bot_name: str
    action: str
    user: str
    channel: str
    message: str
    status: str = "PENDING"


class WebChatQueueManager(QObject):
    """FIFO serializador de tickets para una QWebEngineView."""

    ticket_processed = Signal(str, str)
    ticket_started = Signal(str, str)
    ticket_finished = Signal(str, str)
    queue_error = Signal(str, str)

    def __init__(
        self,
        web_view: QWebEngineView,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.web_view = web_view
        self.msg_queue: queue.Queue[BotTicket] = queue.Queue()
        self.is_busy = False
        self.current_ticket: BotTicket | None = None
        self.protocol_initialized = False

    def initialize_protocol(self) -> None:
        """Inyecta las directrices una sola vez al abrir el SUPER CHAT."""
        if self.protocol_initialized:
            return
        self.protocol_initialized = True
        self._inject_to_browser(
            PROTOCOL_DIRECTIVE,
            callback=self._on_protocol_initialized,
            send=True,
        )

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
            raise ValueError("bot_name no puede estar vacío")
        if not ticket_id.strip():
            raise ValueError("ticket_id no puede estar vacío")
        if not action.strip():
            raise ValueError("action no puede estar vacío")
        if not message.strip():
            raise ValueError("message no puede estar vacío")

        self.msg_queue.put(
            BotTicket(
                ticket_id=ticket_id.strip(),
                bot_name=bot_name.strip(),
                action=action.strip(),
                user=user.strip(),
                channel=channel.strip(),
                message=message.strip(),
            )
        )
        self.process_next()

    def process_next(self) -> None:
        if self.is_busy or self.msg_queue.empty():
            return

        self.current_ticket = self.msg_queue.get()
        self.current_ticket.status = "PROCESSING"
        self.is_busy = True

        ticket = self.current_ticket
        self.ticket_started.emit(ticket.ticket_id, ticket.bot_name)

        prompt = (
            f"({ticket.bot_name}) codigo {ticket.ticket_id} "
            f"#{ticket.action} [{ticket.user}] [{ticket.channel}] "
            f'"{ticket.message}"'
        )
        self._inject_to_browser(
            prompt,
            callback=self._on_ticket_injected,
            send=True,
        )

    def register_ticket_response(self, response_text: str) -> None:
        if self.current_ticket is None:
            return
        self.ticket_processed.emit(
            self.current_ticket.ticket_id,
            response_text.strip(),
        )

    def close_current_ticket(self) -> None:
        ticket = self.current_ticket
        if ticket is None:
            return

        close_prompt = (
            f"({ticket.bot_name}) codigo {ticket.ticket_id} #resuelto"
        )
        self._inject_to_browser(
            close_prompt,
            callback=self._on_close_injected,
            send=True,
        )

    def _on_protocol_initialized(self, result: str) -> None:
        if not result.startswith("OK"):
            self.queue_error.emit("__protocol__", result)

    def _on_ticket_injected(self, result: str) -> None:
        if not result.startswith("OK") and self.current_ticket:
            self.queue_error.emit(self.current_ticket.ticket_id, result)

    def _on_close_injected(self, result: str) -> None:
        ticket = self.current_ticket
        if ticket is None:
            return

        if not result.startswith("OK"):
            self.queue_error.emit(ticket.ticket_id, result)
            return

        ticket.status = "RESOLVED"
        ticket_id = ticket.ticket_id
        bot_name = ticket.bot_name
        self.current_ticket = None
        self.is_busy = False
        self.ticket_finished.emit(ticket_id, bot_name)
        QTimer.singleShot(1000, self.process_next)

    def _inject_to_browser(
        self,
        text: str,
        callback=None,
        send: bool = True,
    ) -> None:
        js_text = json.dumps(text, ensure_ascii=False)
        send_code = """
            setTimeout(() => {
                const btn = document.querySelector(
                    'button[aria-label*="Send"],' +
                    'button[aria-label*="Enviar"],' +
                    'button[data-testid*="send"],' +
                    'button.send-button'
                );
                if (btn && !btn.disabled) {
                    btn.click();
                    return;
                }
            }, 500);
        """ if send else ""

        js_code = f"""
        (() => {{
            const text = {js_text};
            const inputArea = document.querySelector(
                'textarea, div[contenteditable="true"]'
            );
            if (!inputArea) return "ERROR: NO_DOM_INPUT";

            if (inputArea.tagName === "TEXTAREA") {{
                const setter = Object.getOwnPropertyDescriptor(
                    HTMLTextAreaElement.prototype, "value"
                )?.set;
                if (setter) setter.call(inputArea, text);
                else inputArea.value = text;
                inputArea.dispatchEvent(
                    new Event("input", {{ bubbles: true }})
                );
                inputArea.dispatchEvent(
                    new Event("change", {{ bubbles: true }})
                );
            }} else {{
                inputArea.focus();
                inputArea.textContent = text;
                inputArea.dispatchEvent(
                    new InputEvent("input", {{
                        bubbles: true,
                        inputType: "insertText",
                        data: text
                    }})
                );
            }}

            {send_code}
            return "OK: INJECTED";
        }})();
        """
        self.web_view.page().runJavaScript(
            js_code,
            callback or (lambda result: None),
        )
