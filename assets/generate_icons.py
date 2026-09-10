#!/usr/bin/env python3
"""
Script per generare le icone PNG ad alta fedeltà per il tema hicolor di Linux.
"""
from pathlib import Path
import shutil
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
ICONS_DIR = SCRIPT_DIR / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

def generate_png_icon(size: int, output_path: Path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scale = size / 256.0

    # Ombra leggera
    shadow_box = [int(34 * scale), int(42 * scale), int(222 * scale), int(226 * scale)]
    draw.rectangle(shadow_box, fill=(0, 0, 0, 45))

    # Corpo foglietto Post-it
    paper_box = [int(32 * scale), int(40 * scale), int(220 * scale), int(220 * scale)]
    draw.rectangle(paper_box, fill=(254, 240, 138, 255), outline=(234, 179, 8, 255), width=max(1, int(2 * scale)))

    # Nastro superiore adesivo
    tape_box = [int(32 * scale), int(40 * scale), int(220 * scale), int(76 * scale)]
    draw.rectangle(tape_box, fill=(250, 204, 21, 255))

    # Righe di testo simulate
    line_w = max(2, int(6 * scale))
    draw.line([(int(60 * scale), int(105 * scale)), (int(192 * scale), int(105 * scale))], fill=(161, 98, 7, 200), width=line_w)
    draw.line([(int(60 * scale), int(135 * scale)), (int(170 * scale), int(135 * scale))], fill=(161, 98, 7, 200), width=line_w)
    draw.line([(int(60 * scale), int(165 * scale)), (int(145 * scale), int(165 * scale))], fill=(161, 98, 7, 200), width=line_w)

    # Segno di spunta verde
    check_w = max(2, int(7 * scale))
    draw.line([
        (int(150 * scale), int(172 * scale)),
        (int(165 * scale), int(186 * scale)),
        (int(195 * scale), int(152 * scale))
    ], fill=(34, 197, 94, 255), width=check_w)

    # Puntina rossa centrale in alto
    pin_box = [int(116 * scale), int(22 * scale), int(140 * scale), int(46 * scale)]
    draw.ellipse(pin_box, fill=(239, 68, 68, 255), outline=(185, 28, 28, 255), width=max(1, int(2 * scale)))
    shine_box = [int(122 * scale), int(26 * scale), int(130 * scale), int(34 * scale)]
    draw.ellipse(shine_box, fill=(255, 255, 255, 180))

    img.save(output_path, "PNG")
    print(f"Generata icona: {output_path.name} ({size}x{size})")

if __name__ == "__main__":
    sizes = [256, 128, 64, 48, 32]
    for s in sizes:
        generate_png_icon(s, ICONS_DIR / f"icon-{s}.png")
    # Copia 256 come icon.png principale
    shutil.copyfile(ICONS_DIR / "icon-256.png", SCRIPT_DIR / "icon.png")
    print("Completato!")
