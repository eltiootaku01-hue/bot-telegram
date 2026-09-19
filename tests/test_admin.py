from types import SimpleNamespace

from app.core.config import Settings
from app.db.database import Database
from app.modules.admin.module import AdminModule


def test_rare_approval_owner_requires_private_owner_chat() -> None:
    module = AdminModule(
        Database("sqlite+aiosqlite:///:memory:"),
        Settings(admin_user_id=77),
    )

    owner = SimpleNamespace(id=77)
    private_message = SimpleNamespace(
        chat=SimpleNamespace(type="private", id=77),
    )
    group_message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup", id=-100),
    )
    private_callback = SimpleNamespace(from_user=owner, message=private_message)
    group_callback = SimpleNamespace(from_user=owner, message=group_message)

    assert module._is_owner(private_callback) is True
    assert module._is_owner(group_callback) is False
