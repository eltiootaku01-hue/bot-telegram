from app.db.models import FanRequest, MediaAsset
from app.ui.control_keyboards import cami_pending_requests


def test_media_asset_links_to_fan_request() -> None:
    assert "request_id" in MediaAsset.__table__.c
    assert FanRequest.__tablename__ == "fan_requests"


def test_request_callback_stays_within_telegram_limit() -> None:
    markup = cami_pending_requests(123, [(987654, "#987654 · Asuna con traje de conejita")])
    callback_data = markup.inline_keyboard[0][0].callback_data
    assert callback_data == "cami:req:link:123:987654"
    assert len(callback_data) <= 64
