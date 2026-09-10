from bot_ia.interfaces.telegram import TelegramApiClient, TelegramConfigurationError, TelegramInputError, TelegramOutbound

# Existing Phase 7 tests continue to exercise the adapter/client contract.
# Long outbound replies are now split into Telegram-safe chunks instead of being rejected.

# ...
