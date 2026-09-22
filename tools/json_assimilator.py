import json
import os
import glob
import hashlib

# Directorios de la trinchera
RAW_DATA_DIR = "assets/raw/data/"
OUTPUT_DATA_FILE = "engine/waifumon/src/main/resources/waifumon/cards-dataset.json"

# Mapeo de elementos de chatarra (Ej: Tipos de Pokémon/RPG Maker a WaifuMon)
ELEMENT_MAP = {
    "fire": "fuego", "water": "agua", "grass": "tierra", "electric": "rayo",
    "psychic": "mente", "dark": "oscuridad", "fairy": "arcano", "normal": "neutro"
}

def generate_id(name):
    # Genera un ID único si la chatarra no lo trae
    return "wfm_" + hashlib.md5(name.encode()).hexdigest()[:8]

def assimilate_raw_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    assimilated_cards = []
    
    # Asume que la chatarra viene en una lista o diccionario
    items = raw_data.values() if isinstance(raw_data, dict) else raw_data
    
    for item in items:
        # Forzar el mapeo de la chatarra a nuestro esquema estricto
        card = {
            "card_id": str(item.get("id", generate_id(item.get("name", "Unknown")))),
            "name": item.get("name", "Scavenged Waifu"),
            # Si robaron stats de Pokémon (hp, atk, def, spatk), los normalizamos:
            "base_hp": item.get("base_hp", item.get("hp", 100)),
            "base_atk": item.get("base_atk", item.get("attack", item.get("atk", 10))),
            "base_def": item.get("base_def", item.get("defense", item.get("def", 10))),
            "cost": item.get("cost", item.get("mana", 1)),
            "element_type": ELEMENT_MAP.get(str(item.get("type", "normal")).lower(), "neutro"),
            "skills": [],
            "status_effects": []
        }
        
        # Procesar habilidades robadas
        raw_moves = item.get("moves", item.get("skills", []))
        for move in raw_moves[:2]: # Solo tomamos 2 skills por carta para no romper la UI
            skill = {
                "skill_id": move.get("id", generate_id(move.get("name", "Attack"))),
                "name": move.get("name", "Golpe Básico"),
                "power": move.get("power", move.get("basePower", 40)),
                "category": "damage",
                "crit_rate": move.get("crit_rate", 5),
                "crit_multiplier": 1.5,
                "element_multiplier": 1.0
            }
            card["skills"].append(skill)
            
        assimilated_cards.append(card)
        
    return assimilated_cards

def run_assimilation():
    print("=== INICIANDO ASIMILACIÓN DE DATASETS JSON ===")
    all_cards = []
    
    for file in glob.glob(f"{RAW_DATA_DIR}/*.json"):
        print(f"[PROCESANDO] Extrayendo ADN de {file}...")
        all_cards.extend(assimilate_raw_json(file))
        
    # Empaquetar y guardar para el Java Engine
    dataset = {"cards": all_cards}
    
    os.makedirs(os.path.dirname(OUTPUT_DATA_FILE), exist_ok=True)
    with open(OUTPUT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        
    print(f"[OK] {len(all_cards)} cartas inyectadas en {OUTPUT_DATA_FILE}.")
    print("El Motor Java ya puede consumir este archivo.")

if __name__ == "__main__":
    run_assimilation()
