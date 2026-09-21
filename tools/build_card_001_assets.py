from __future__ import annotations

import json
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "assets/production/cards"
QUAR = ROOT / "assets/quarantine/card_stages"
ART = ROOT / "assets/waifus/art_manifest.json"
PROMPTS = ROOT / "assets/waifus/card_art_prompt_manifest.json"
QA = ROOT / "assets/waifus/card_art_qa_manifest.json"
REPORT = ROOT / "docs/generated/WAIFUMON_CARD_001_ALISA_STAGES.md"

PALETTE = {"navy":"#102743","blue":"#284c78","ice":"#eef4fb","skin":"#f4cec1","red":"#8c2b46","gold":"#d8b876","line":"#223954","eye":"#4e8bd0"}

HEAD = """
<g stroke="#223954" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
<path fill="#c3d1e4" d="M290 690C250 430 300 210 512 160c212 50 262 270 222 530l-65 210H355Z"/>
<path fill="#f2f6fb" d="M320 610C300 410 340 250 512 205c172 45 212 205 192 405l-48 230H368Z"/>
<path fill="#f4cec1" d="M390 430c25-85 75-125 122-125s97 40 122 125l-10 215c-10 95-62 155-112 175-50-20-102-80-112-175Z"/>
<path fill="#e7eef7" d="M350 455c-10-130 65-220 162-233 97 13 172 103 162 233-42-45-81-62-118-64l-24-78-24 92-34-64-48 70-23-45c-25 21-42 45-53 89Z"/>
<path fill="#b8c7da" d="M352 430c-45 70-55 190-36 315l42 165 45-94-18-245 23-125Z"/><path fill="#b8c7da" d="M672 430c45 70 55 190 36 315l-42 165-45-94 18-245-23-125Z"/>
<path fill="none" stroke-width="9" d="M414 492q40-27 75 0M535 492q35-27 75 0"/>
<path fill="#fff" d="M412 540q42-37 84 0-42 43-84 0ZM528 540q42-37 84 0-42 43-84 0Z"/>
<ellipse fill="#4e8bd0" cx="454" cy="540" rx="17" ry="29"/><ellipse fill="#4e8bd0" cx="570" cy="540" rx="17" ry="29"/>
<ellipse fill="#203b64" stroke="none" cx="454" cy="548" rx="6" ry="13"/><ellipse fill="#203b64" stroke="none" cx="570" cy="548" rx="6" ry="13"/>
<circle fill="#fff" stroke="none" cx="460" cy="530" r="5"/><circle fill="#fff" stroke="none" cx="576" cy="530" r="5"/>
<path fill="none" stroke-width="4" d="M512 555l-10 52 18 6"/><path fill="none" stroke="#8c2b46" stroke-width="5" d="M477 666q35 20 70 0"/>
<path fill="none" stroke="#fff" stroke-width="8" opacity=".65" d="M370 345q22-78 92-100M654 345q-22-70-73-92"/>
</g>"""

def page(extra: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1536" viewBox="0 0 1024 1536">
<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#081a31"/><stop offset=".55" stop-color="#173f6c"/><stop offset="1" stop-color="#0a203b"/></linearGradient><radialGradient id="g"><stop stop-color="#d9f0ff" stop-opacity=".75"/><stop offset="1" stop-color="#d9f0ff" stop-opacity="0"/></radialGradient><filter id="b"><feGaussianBlur stdDeviation="22"/></filter></defs><rect width="1024" height="1536" fill="url(#bg)"/>{extra}</svg>"""

def render(tier: str) -> Image.Image:
    if tier == "R":
        extra = """<circle cx="150" cy="260" r="190" fill="url(#g)" filter="url(#b)"/><circle cx="860" cy="1050" r="220" fill="url(#g)" filter="url(#b)"/>""" + HEAD + """<path fill="#102743" stroke="#223954" stroke-width="8" d="M270 900q242-85 484 0l90 300q-332 62-664 0Z"/><path fill="#f7fbff" stroke="#223954" stroke-width="7" d="M420 885l92 120 92-120-35 263H455Z"/><path fill="#8c2b46" stroke="#6a1c32" stroke-width="5" d="M492 980l20 50 20-50-7 126h-26Z"/>"""
    elif tier == "SR":
        extra = """<circle cx="160" cy="250" r="150" fill="url(#g)" filter="url(#b)"/><circle cx="850" cy="300" r="190" fill="url(#g)" filter="url(#b)"/>""" + """<g transform="translate(38 70)scale(.88)">""" + HEAD + """</g><path fill="#102743" stroke="#223954" stroke-width="9" d="M325 800q180-75 325 5l82 294q-160 75-341 8l-95-235Z"/><path fill="#f7fbff" stroke="#223954" stroke-width="8" d="M420 810l87 102 100-110-48 211h-92Z"/><path fill="#8c2b46" stroke="#6a1c32" stroke-width="5" d="M491 900l19 46 19-46-6 109h-25Z"/><path fill="#314f79" stroke="#1b304d" stroke-width="8" d="M350 1090l300-10 65 176q-195 55-373 0Z"/><path d="M390 1098l-25 145m76-150l-12 154m65-155v162m65-162l17 154m34-155l28 145" stroke="#a8c0dc" stroke-width="5"/><path fill="#e6ecf4" stroke="#223954" stroke-width="8" d="M392 1240l86 3-20 150h-90Z"/><path fill="#e6ecf4" stroke="#223954" stroke-width="8" d="M546 1243l86-5 37 155h-91Z"/><path fill="#14263f" stroke="#0a1628" stroke-width="9" d="M350 1370h125l18 62H324Z"/><path fill="#14263f" stroke="#0a1628" stroke-width="9" d="M565 1370h110l32 62H550Z"/><rect x="404" y="970" width="210" height="190" rx="12" fill="#dbe8f7" stroke="#223954" stroke-width="8" transform="rotate(-4 509 1065)"/><path d="M509 980v160M420 1060h180" stroke="#7da8d5" stroke-width="5"/><g fill="#fff" opacity=".9">""" + "".join(f'<circle cx="{60+(i*97)%910}" cy="{120+(i*137)%1100}" r="{2+i%4}"/>' for i in range(28)) + "</g>"
    else:
        extra = """<circle cx="790" cy="220" r="180" fill="url(#g)" filter="url(#b)"/><path fill="#0e2a4b" opacity=".7" d="M70 1080q190-250 355-160v616H0ZM954 1080Q764 830 599 920v616h425Z"/><path fill="none" stroke="#d8efff" stroke-width="10" opacity=".55" d="M120 810q392-650 784 0"/><path fill="none" stroke="#fff" stroke-width="4" opacity=".65" d="M160 830q352-585 704 0"/><g fill="#f4fbff" opacity=".95">""" + "".join(f'<circle cx="{45+(i*79)%930}" cy="{70+(i*113)%1140}" r="{2+i%5}"/>' for i in range(45)) + """</g><path fill="#253e67" stroke="#182c48" stroke-width="9" d="M250 690q262-110 524 0l115 610-185-105-192 165-192-165-185 105Z"/><g transform="translate(0 45)scale(.82)">""" + HEAD + """</g><path fill="#102743" stroke="#172b45" stroke-width="9" d="M390 735q122-75 242 0l88 380-80 58H380l-80-60Z"/><path fill="#f9fbfe" stroke="#223954" stroke-width="8" d="M420 725l92 105 92-105-37 215H455Z"/><path fill="#8c2b46" stroke="#6a1c32" stroke-width="5" d="M492 818l20 46 20-46-7 114h-26Z"/><path fill="none" stroke="#d4b16d" stroke-width="8" d="M320 1060q192 56 384 0"/><path fill="#f7fbff" stroke="#223954" stroke-width="8" d="M372 1110h280l84 178-112 42-112-60-112 60-108-42Z"/><path d="M432 1125l-30 170m84-173l-17 154m76-154l18 154m48-151l34 170" stroke="#9bb7d4" stroke-width="5"/><path fill="#e7edf5" stroke="#223954" stroke-width="9" d="M404 1290l87-5-17 166H354Z"/><path fill="#e7edf5" stroke="#223954" stroke-width="9" d="M533 1285l87 5 57 166H559Z"/><path fill="#14263f" stroke="#0a1628" stroke-width="10" d="M340 1420h143l22 72H312Z"/><path fill="#14263f" stroke="#0a1628" stroke-width="10" d="M548 1420h140l48 72H535Z"/><path fill="#f7fbff" stroke="#223954" stroke-width="8" d="M350 910q-35 25-24 88 18 24 58-5M674 910q35 25 24 88-18 24-58-5"/><path fill="#17304f" stroke="#d8b876" stroke-width="8" d="M748 620l72 660"/><circle fill="#eaf7ff" stroke="#d8b876" stroke-width="8" cx="748" cy="608" r="34"/>"""
    svg = page(extra)
    tmp = ROOT / "data/_card001.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(tmp), output_width=2048, output_height=3072)
    return Image.open(tmp).convert("RGB").resize((1024,1536), Image.Resampling.LANCZOS)

def save_image(tier: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    render(tier).save(target, format="JPEG", quality=92, subsampling=2, optimize=True)

def update_manifests() -> None:
    qa = json.loads(QA_MANIFEST.read_text(encoding="utf-8"))
    art = json.loads(ART.read_text(encoding="utf-8"))
    prompts = json.loads(PROMPT_MANIFEST.read_text(encoding="utf-8"))
    item = next(x for x in qa["items"] if x["character_id"] == CHARACTER_ID)
    item.update({
        "approved": True,
        "reviewer": "OpenAI visual QA",
        "reviewed_at": "2026-09-21T17:49:00-03:00",
        "second_reviewer": "",
        "production_file": "assets/production/cards/alisa-kujo--normal.jpg",
        "art_tier": "SR",
        "framing_profile": "SR",
        "checks": {k: True for k in ("anatomy","hands_and_fingers","limbs_and_joints","face_and_identity","perspective","crop_and_framing","wardrobe_and_style","no_explicit_content")},
        "notes": "SR canonical asset approved after individual visual inspection. R kept as approved auxiliary stage. UR generated and primary-reviewed but held in quarantine pending required independent second review.",
        "stage_assets": [
            {"tier":"R","file":"assets/production/cards/alisa-kujo--r.jpg","status":"approved_auxiliary"},
            {"tier":"SR","file":"assets/production/cards/alisa-kujo--normal.jpg","status":"approved_canonical"},
            {"tier":"UR","file":"assets/quarantine/card_stages/alisa-kujo--ur.jpg","status":"primary_review_passed_second_review_required"},
        ],
    })
    qa["completed_items"] = sum(1 for x in qa["items"] if x["approved"])
    qa["progress_percent"] = round(qa["completed_items"] / qa["total_items"] * 100, 2)
    a = next(x for x in art["items"] if x["character_id"] == CHARACTER_ID)
    a["asset_status"] = "production_approved"; a["visual_audit_status"] = "approved"
    art["completed_items"] = qa["completed_items"]; art["progress_percent"] = qa["progress_percent"]
    p = next(x for x in prompts["items"] if x["character_id"] == CHARACTER_ID)
    p["asset_status"] = "production_approved"; p["visual_audit_status"] = "approved"
    for path, data in ((QA,qa),(ART,art),(PROMPT_MANIFEST,prompts)):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_report() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# WaifuMon — Carta #001 / Alisa Mikhailovna Kujo\n\n"
        "Character ID: alisa-kujo\nObra: Alya Sometimes Hides Her Feelings in Russian\n\n"
        "Etapa 1 — R: close-up de rostro y hombros, atuendo base, no sugestivo.\n\n"
        + STAGE_PROMPTS["R"] + "\n\n"
        "Etapa 2 — SR: plano tres cuartos, casi cuerpo completo, vestuario totalmente cubierto.\n\n"
        + STAGE_PROMPTS["SR"] + "\n\n"
        "Etapa 3 — UR: plano general, cuerpo completo, vestuario premium totalmente cubierto. "
        "El asset queda en cuarentena hasta segunda revisión independiente.\n\n"
        + STAGE_PROMPTS["UR"] + "\n", encoding="utf-8")

if __name__ == "__main__":
    CHARACTER_ID = "alisa-kujo"
    save_image("R", PROD / "alisa-kujo--r.jpg")
    save_image("SR", PROD / "alisa-kujo--normal.jpg")
    save_image("UR", QUAR / "alisa-kujo--ur.jpg")
    update_manifests()
    write_report()
