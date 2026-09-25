# -*- coding: utf-8 -*-
"""Motor Playwright aislado para la automatización web de Café Otaku.

Este módulo mantiene un pool pequeño y fijo de páginas Chromium, una por
personaje, con selectores OR cargados desde configuración externa.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from playwright.async_api import Locator, Page, async_playwright


GEMINI_URL = "https://gemini.google.com"
WAITRESS_IDS = (
    "cari",
    "cami",
    "sunna",
    "chie",
    "chloe",
    "scarlet",
)
DEFAULT_SELECTOR_CONFIG = Path("src/config/selectors.json")
PAGE_TIMEOUT_MS = 15_000
RESPONSE_TIMEOUT_MS = 10_000
NAVIGATION_TIMEOUT_MS = 20_000
SOFT_RESET_AFTER_INTERACTIONS = 20

LIGHTWEIGHT_CHROMIUM_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--hide-crash-restore-bubble",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-sandbox",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-client-side-phishing-detection",
    "--disable-default-apps",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--no-zygote",
    "--renderer-process-limit=2",
)


def _lightweight_browser_args(*, headless: bool) -> list[str]:
    args = list(LIGHTWEIGHT_CHROMIUM_ARGS)
    if headless:
        args.insert(0, "--headless=new")
        if os.getenv("PLAYWRIGHT_DISABLE_IMAGES", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            args.append("--blink-settings=imagesEnabled=false")
    return args


class SelectorResolver:
    """Resuelve selectores OR desde el archivo compartido de configuración."""

    def __init__(
        self,
        config_path: str | Path = DEFAULT_SELECTOR_CONFIG,
    ) -> None:
        path = Path(config_path)
        with path.open("r", encoding="utf-8") as file:
            self._data = json.load(file)

    def get(self, key: str) -> str:
        """Devuelve un selector CSS OR listo para Playwright."""
        entry = self._data["gemini_web"].get(key, [])

        if isinstance(entry, list):
            return ", ".join(
                str(selector)
                for selector in entry
                if str(selector).strip()
            )

        return str(entry)


class WebQueueManager:
    """Pool Playwright con seis páginas aisladas por personaje.

    La clase no comparte páginas entre personajes. El contador de
    interacciones permite aplicar un soft reset preventivo para liberar
    estado acumulado de la SPA sin cerrar todo Chromium.
    """

    def __init__(
        self,
        selector_config_path: str | Path = DEFAULT_SELECTOR_CONFIG,
        *,
        headless: bool = True,
    ) -> None:
        self.playwright: Any | None = None
        self.browser: Any | None = None
        self.context: Any | None = None
        self.pages: dict[str, Page] = {}
        self.interaction_counters: dict[str, int] = {}
        self.selectors = SelectorResolver(selector_config_path)
        self.headless = headless
        self._closing = False

    async def init_browser_pool(self) -> None:
        """Inicializa Chromium y abre seis pestañas aisladas por mesera."""
        if self.context is not None and self.pages:
            return

        self._closing = False
        self.playwright = await async_playwright().start()

        try:
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=_lightweight_browser_args(
                    headless=self.headless,
                ),
            )
            self.context = await self.browser.new_context()

            for waitress_id in WAITRESS_IDS:
                page = await self.context.new_page()
                await page.goto(
                    GEMINI_URL,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
                self.pages[waitress_id] = page
                self.interaction_counters[waitress_id] = 0
        except Exception:
            await self.close_browser_pool()
            raise

    async def soft_reset_page(self, waitress_id: str) -> None:
        """Recarga limpia la SPA durante el ciclo de descanso del personaje."""
        page = self.pages[waitress_id]

        try:
            await page.reload(
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT_MS,
            )
        except Exception:
            await page.goto(
                GEMINI_URL,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )

        self.interaction_counters[waitress_id] = 0

    async def get_active_locator(
        self,
        page: Page,
        selector_key: str,
        *,
        timeout_ms: int = RESPONSE_TIMEOUT_MS,
    ) -> Locator:
        """Obtiene el primer elemento realmente visible e interactuable.

        Se excluyen candidatos que contengan nodos marcados con "hidden" y
        se valida la visibilidad computada de cada candidato. Esto cubre
        elementos ocultos directamente y elementos dentro de contenedores
        ocultos.
        """
        selector_str = self.selectors.get(selector_key)

        if not selector_str:
            raise LookupError(
                f"No hay selectores configurados para {selector_key!r}"
            )

        candidates = page.locator(selector_str).filter(
            has_not=page.locator("[hidden]"),
        )

        deadline = timeout_ms / 1000
        started = 0.0

        while True:
            locator_count = await candidates.count()

            for index in range(locator_count):
                candidate = candidates.nth(index)

                try:
                    if await candidate.is_visible():
                        return candidate
                except Exception:
                    continue

            if started >= deadline:
                break

            await page.wait_for_timeout(100)
            started += 0.1

        raise LookupError(
            f"No se encontró un elemento visible para {selector_key!r}"
        )

    async def process_task(
        self,
        waitress_id: str,
        payload: dict[str, Any],
    ) -> str:
        """Ejecuta una interacción completa y devuelve la respuesta textual."""
        if self._closing:
            raise RuntimeError("WebQueueManager está cerrándose")

        page = self.pages[waitress_id]
        prompt = str(payload.get("prompt", "")).strip()

        if not prompt:
            raise ValueError("El payload requiere un prompt no vacío")

        textarea = await self.get_active_locator(
            page,
            "prompt_textarea",
        )
        await textarea.fill(prompt)

        send_button = await self.get_active_locator(
            page,
            "send_button",
        )
        await send_button.click()

        response_locator = await self.get_active_locator(
            page,
            "response_bubble",
            timeout_ms=RESPONSE_TIMEOUT_MS,
        )
        response_text = (
            await response_locator.inner_text()
        ).strip()

        self.interaction_counters[waitress_id] = (
            self.interaction_counters.get(waitress_id, 0) + 1
        )

        if (
            self.interaction_counters[waitress_id]
            >= SOFT_RESET_AFTER_INTERACTIONS
        ):
            await self.soft_reset_page(waitress_id)

        return response_text

    async def close_browser_pool(self) -> None:
        """Cierre limpio e idempotente de Chromium y Playwright."""
        if self._closing:
            return

        self._closing = True

        context = self.context
        browser = self.browser
        playwright = self.playwright

        self.pages.clear()
        self.interaction_counters.clear()
        self.context = None
        self.browser = None
        self.playwright = None

        if context is not None:
            try:
                await context.close()
            except Exception:
                pass

        if browser is not None:
            try:
                is_connected = getattr(browser, "is_connected", None)
                if is_connected is None or is_connected():
                    await browser.close()
            except Exception:
                pass

        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass

        self._closing = False
