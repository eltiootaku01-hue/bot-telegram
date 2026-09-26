# -*- coding: utf-8 -*-

import math


def safe_stat_calculation(
    base_value: int,
    percentage_modifier: float,
    flat_modifier: int
) -> int:
    """
    Aplica modificadores de forma segura.

    - Evita resultados negativos.
    - Trunca hacia abajo con math.floor().
    - Rechaza valores no finitos para evitar NaN/Infinity.
    """
    if not isinstance(base_value, int) or isinstance(base_value, bool):
        raise TypeError("base_value debe ser un entero.")
    if not isinstance(flat_modifier, int) or isinstance(flat_modifier, bool):
        raise TypeError("flat_modifier debe ser un entero.")
    if not isinstance(percentage_modifier, (int, float)) or isinstance(percentage_modifier, bool):
        raise TypeError("percentage_modifier debe ser numérico.")

    if not math.isfinite(float(base_value)):
        raise ValueError("base_value debe ser finito.")
    if not math.isfinite(float(flat_modifier)):
        raise ValueError("flat_modifier debe ser finito.")
    if not math.isfinite(float(percentage_modifier)):
        raise ValueError("percentage_modifier debe ser finito.")

    total = (base_value + flat_modifier) * (1.0 + float(percentage_modifier))
    return max(0, math.floor(total))


def calculate_combat_stats(
    waifu_base_atk: int,
    waifu_base_def: int,
    equip_atk_mod: int,
    equip_def_mod: int,
    magic_effect_code: str
) -> dict:
    """
    Calcula ATK y DEF finales aplicando equipamiento y cartas mágicas.

    Los modificadores pasan por safe_stat_calculation() para mantener una
    única ruta de saneamiento matemático.
    """
    total_atk = safe_stat_calculation(
        waifu_base_atk, 0.0, equip_atk_mod
    )
    total_def = safe_stat_calculation(
        waifu_base_def, 0.0, equip_def_mod
    )
    double_attack = False

    if magic_effect_code == "BERSERK_FORCE":
        total_atk = safe_stat_calculation(total_atk, 0.30, 0)
        total_def = safe_stat_calculation(total_def, -0.30, 0)
    elif magic_effect_code == "SHIELD_WALL":
        total_def = safe_stat_calculation(total_def, 0.50, 0)
        total_atk = safe_stat_calculation(total_atk, -0.20, 0)
    elif magic_effect_code == "DOUBLE_ATTACK":
        total_def = safe_stat_calculation(total_def, -0.20, 0)
        double_attack = True

    return {
        "atk": total_atk,
        "def": total_def,
        "double_attack": double_attack
    }
