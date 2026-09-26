# -*- coding: utf-8 -*-

import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import ActiveMatch, Base
from src.services.battle_service import (
    DEFAULT_INITIAL_HP,
    MINIMUM_DAMAGE_FLOOR,
    calculate_combat_stats,
    execute_turn,
    safe_stat_calculation,
)


@pytest.fixture(scope="function")
def db_session():
    """Crea una base SQLite en memoria aislada para cada prueba."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_match(db_session):
    """Crea un duelo activo mínimo compatible con el modelo actual."""
    match = ActiveMatch(
        id="match-test-uuid-001",
        group_id=-100123456789,
        player1_id=1001,
        player2_id=2002,
        status="IN_PROGRESS",
        current_turn_id=1001,
        current_turn_player_id=1001,
        p1_hp=DEFAULT_INITIAL_HP,
        p2_hp=DEFAULT_INITIAL_HP,
        staked_rarity="R",
    )
    db_session.add(match)
    db_session.commit()
    return match


class TestStatCalculations:
    def test_safe_stat_calculation_truncation_and_floor(self):
        """Trunca hacia abajo y evita estadísticas negativas."""
        result = safe_stat_calculation(
            base_value=1000,
            percentage_modifier=0.15,
            flat_modifier=50,
        )
        assert result == 1207

        result_negative = safe_stat_calculation(
            base_value=100,
            percentage_modifier=-2.0,
            flat_modifier=0,
        )
        assert result_negative == 0

    def test_calculate_combat_stats_default_and_equip(self):
        """Combina estadísticas base con equipamiento."""
        waifu = {"base_atk": 1000, "base_def": 800}
        equip = {"flat_atk_bonus": 150, "flat_def_bonus": 50}

        stats = calculate_combat_stats(waifu, equip, magic=None)

        assert stats["atk"] == 1150
        assert stats["def"] == 850
        assert stats["double_attack"] is False
        assert stats["heal_amount"] == 0

    def test_magic_effect_berserk_force(self):
        """BERSERK_FORCE aplica +30% ATK y -30% DEF."""
        stats = calculate_combat_stats(
            {"base_atk": 1000, "base_def": 1000},
            magic={"effect_code": "BERSERK_FORCE"},
        )

        assert stats["atk"] == 1300
        assert stats["def"] == 700

    def test_magic_effect_shield_wall(self):
        """SHIELD_WALL aplica +50% DEF y -20% ATK."""
        stats = calculate_combat_stats(
            {"base_atk": 1000, "base_def": 1000},
            magic={"effect_code": "SHIELD_WALL"},
        )

        assert stats["atk"] == 800
        assert stats["def"] == 1500

    def test_magic_effect_double_attack(self):
        """DOUBLE_ATTACK activa doble golpe y reduce DEF un 20%."""
        stats = calculate_combat_stats(
            {"base_atk": 1000, "base_def": 1000},
            magic={"effect_code": "DOUBLE_ATTACK"},
        )

        assert stats["double_attack"] is True
        assert stats["def"] == 800

    def test_magic_effect_basic_heal(self):
        """BASIC_HEAL concede +250 HP de recuperación."""
        stats = calculate_combat_stats(
            {"base_atk": 500, "base_def": 500},
            magic={"effect_code": "BASIC_HEAL"},
        )

        assert stats["heal_amount"] == 250


class TestExecuteTurn:
    @patch("src.services.battle_service._load_player_deck")
    def test_execute_turn_out_of_turn_rejected(
        self,
        mock_load_deck,
        db_session,
        sample_match,
    ):
        """Rechaza una acción cuando el jugador no tiene el turno."""
        result = execute_turn(
            session=db_session,
            match_id=sample_match.id,
            acting_player_id=2002,
            action_type="ATTACK",
        )

        assert result["success"] is False
        assert "No es tu turno" in result["error"]
        mock_load_deck.assert_not_called()

    @patch("src.services.battle_service._load_player_deck")
    def test_execute_turn_standard_attack_and_damage_floor(
        self,
        mock_load_deck,
        db_session,
        sample_match,
    ):
        """Garantiza el daño mínimo cuando DEF supera a ATK."""
        mock_load_deck.side_effect = [
            {
                "waifu": {"base_atk": 500, "base_def": 500},
                "equipment": None,
                "magic": None,
            },
            {
                "waifu": {"base_atk": 500, "base_def": 900},
                "equipment": None,
                "magic": None,
            },
        ]

        result = execute_turn(
            session=db_session,
            match_id=sample_match.id,
            acting_player_id=1001,
            action_type="ATTACK",
        )

        assert result["success"] is True
        assert result["damage_dealt"] == MINIMUM_DAMAGE_FLOOR
        assert result["defender_hp"] == DEFAULT_INITIAL_HP - MINIMUM_DAMAGE_FLOOR
        assert result["next_turn_player_id"] == 2002
        assert result["match_ended"] is False

    @patch("src.services.battle_service.finish_match")
    @patch("src.services.battle_service._load_player_deck")
    def test_execute_turn_knockout_and_finish_match(
        self,
        mock_load_deck,
        mock_finish,
        db_session,
        sample_match,
    ):
        """Finaliza formalmente el duelo cuando el defensor llega a 0 HP."""
        sample_match.p2_hp = 100
        db_session.commit()

        mock_load_deck.side_effect = [
            {
                "waifu": {"base_atk": 1000, "base_def": 500},
                "equipment": None,
                "magic": None,
            },
            {
                "waifu": {"base_atk": 500, "base_def": 700},
                "equipment": None,
                "magic": None,
            },
        ]
        mock_finish.return_value = (True, "Duelo finalizado correctamente.")

        result = execute_turn(
            session=db_session,
            match_id=sample_match.id,
            acting_player_id=1001,
            action_type="ATTACK",
        )

        assert result["success"] is True
        assert result["damage_dealt"] == 300
        assert result["defender_hp"] == 0
        assert result["match_ended"] is True
        assert result["winner_id"] == 1001

        mock_finish.assert_called_once_with(
            db_session,
            match_id=sample_match.id,
            winner_id=1001,
        )
