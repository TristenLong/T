import sys
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

png = sys.argv[1]
img = Image.open(png).convert("L")
# Upscale small game canvases for legible small text (NES HUD is tiny).
w, h = img.size
scale = max(1, int(1600 / max(1, w)))
if scale > 1:
    img = img.resize((w * scale, h * scale), Image.LANCZOS)
txt = pytesseract.image_to_string(img)
pix = list(img.convert("L").resize((80, 40)).getdata())
dark = sum(1 for v in pix if v < 40)
bright = sum(1 for v in pix if v > 180)
out = " ".join(txt.split())
sys.stdout.write(f"TEXT={out} | dark={dark} bright={bright} total={len(pix)}\n")