from aiogram import Dispatcher

from app.core.module import BotModule


class ModuleRegistry:
    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher
        self.modules: dict[str, BotModule] = {}

    def register(self, module: BotModule) -> None:
        if module.name in self.modules:
            raise ValueError(f"Module already registered: {module.name}")
        module.setup()
        self.modules[module.name] = module
        self.dispatcher.include_router(module.router)
