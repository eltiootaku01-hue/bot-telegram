import os
from PIL import Image

INPUT_DIR = "assets/raw/sprites/quarantine/"
OUTPUT_DIR = "assets/production/sprites/"

def remove_background(image_path, output_path, tolerance=30):
    img = Image.open(image_path).convert("RGBA")
    datas = img.getdata()

    # Toma el píxel superior izquierdo (0,0) como referencia de color de fondo
    bg_color = datas[0][:3]

    new_data = []
    for item in datas:
        # Calcula diferencia cromática con respecto al color de fondo
        r_diff = abs(item[0] - bg_color[0])
        g_diff = abs(item[1] - bg_color[1])
        b_diff = abs(item[2] - bg_color[2])

        # Si el color coincide dentro del margen de tolerancia, vuelve transparente el píxel
        if r_diff <= tolerance and g_diff <= tolerance and b_diff <= tolerance:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)

    img.putdata(new_data)
    
    # Redimensiona al estándar de sprite de combate (128x128)
    img = img.resize((128, 128), Image.Resampling.LANCZOS)
    
    img.save(output_path, "PNG")
    print(f"[PROCESADO] Asset generado: {output_path}")

def process_quarantine():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(INPUT_DIR):
        print(f"[ALERTA] La carpeta {INPUT_DIR} no existe. Créala y coloca los PNGs descargados ahí.")
        return

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not files:
        print(f"[VACÍO] No hay imágenes en {INPUT_DIR} para procesar.")
        return

    print(f"=== INICIANDO LIMPIEZA DE {len(files)} SPRITES EN CUARENTENA ===")
    for filename in files:
        in_path = os.path.join(INPUT_DIR, filename)
        
        # Formato de salida uniforme para el engine: <id>_idle.png
        clean_name = os.path.splitext(filename)[0].lower().replace(" ", "_")
        out_path = os.path.join(OUTPUT_DIR, f"{clean_name}_idle.png")
        
        remove_background(in_path, out_path)

if __name__ == "__main__":
    process_quarantine()
