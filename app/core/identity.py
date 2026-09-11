from dataclasses import dataclass
from enum import StrEnum


class BotIdentity(StrEnum):
    CARI = "cari"
    SUNNA = "sunna"
    CAMI = "cami"
    CHIE = "chie"


@dataclass(frozen=True, slots=True)
class IdentityProfile:
    identity: BotIdentity
    display_name: str
    role: str


PROFILES: dict[BotIdentity, IdentityProfile] = {
    BotIdentity.CARI: IdentityProfile(BotIdentity.CARI, "Cari", "Comunidad, conversación y moderación"),
    BotIdentity.SUNNA: IdentityProfile(BotIdentity.SUNNA, "Sunna", "WaifuMon, colección y juego"),
    BotIdentity.CAMI: IdentityProfile(BotIdentity.CAMI, "Cami", "Analítica, archivo y diagnóstico"),
    BotIdentity.CHIE: IdentityProfile(BotIdentity.CHIE, "Chie", "Coordinación, recados y avisos"),
}


def get_profile(identity: BotIdentity) -> IdentityProfile:
    return PROFILES[identity]
