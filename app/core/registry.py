from aiogram import Bot, Dispatcher

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

    def attach_lifecycle(self, bot: Bot) -> None:
        for module in self.modules.values():
            self.dispatcher.startup.register(module.on_startup)
            self.dispatcher.shutdown.register(module.on_shutdown)
