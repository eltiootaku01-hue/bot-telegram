# -*- coding: utf-8 -*-

def calculate_combat_stats(
    waifu_base_atk: int,
    waifu_base_def: int,
    equip_atk_mod: int,
    equip_def_mod: int,
    magic_effect_code: str
) -> dict:
    """
    Calcula ATK y DEF finales aplicando equipamiento y cartas mágicas.

    Efectos de Magia soportados:
    - DOUBLE_ATTACK: otorga 2 ataques por turno y reduce DEF un 20%.
    - BERSERK_FORCE: +30% ATK y -30% DEF.
    - SHIELD_WALL: +50% DEF y -20% ATK.
    """
    # 1. Aplicar bonos fijos de equipamiento.
    total_atk = max(0, waifu_base_atk + equip_atk_mod)
    total_def = max(0, waifu_base_def + equip_def_mod)
    double_attack = False

    # 2. Aplicar modificadores porcentuales de cartas mágicas.
    if magic_effect_code == "BERSERK_FORCE":
        total_atk = int(total_atk * 1.30)
        total_def = int(total_def * 0.70)
    elif magic_effect_code == "SHIELD_WALL":
        total_def = int(total_def * 1.50)
        total_atk = int(total_atk * 0.80)
    elif magic_effect_code == "DOUBLE_ATTACK":
        total_def = int(total_def * 0.80)
        double_attack = True

    return {
        "atk": total_atk,
        "def": total_def,
        "double_attack": double_attack
    }
