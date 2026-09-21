from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SpriteAssetDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    idle: str
    attack: str
    hit: str


class CombatFighterDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    anime: str
    rarity: str
    level: int = Field(ge=1, le=30)
    team: str
    card_url: str
    sprites: SpriteAssetDTO


class CombatInitDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str
    player_id: int
    community_id: int
    asset_contract: dict[str, object]
    team: list[CombatFighterDTO]
    opponents: list[CombatFighterDTO]


class CombatActionDTO(BaseModel):
    action: str = Field(pattern=r"^(attack|special|defend)$")
    attacker_id: str = Field(min_length=1, max_length=100)
    defender_id: str = Field(min_length=1, max_length=100)
    turn_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)


class TurnResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str
    request_id: str
    turn_id: str
    attacker: str
    defender: str
    action: str
    damage: int = Field(ge=0)
    critical: bool
    defender_hp: int = Field(ge=0)
    defender_max_hp: int = Field(gt=0)
    events: list[str] = Field(default_factory=list)
    rewards: list[str] = Field(default_factory=list)


class InvoiceRequestDTO(BaseModel):
    product: str = Field(pattern=r"^(premium_ticket|starter_pack)$")


class InvoiceResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    product: str
    currency: str
    amount: int = Field(gt=0)
    invoice_link: str
    payload: str
