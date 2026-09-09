import sys
from PIL import Image
import pytesseract

# dd_score.py <png> <x> <y> <w> <h> -> digit OCR of a region (the Dig Dug 1UP
# score strip). Crops, upscales, thresholds, reads ONE LINE of digits only.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

png = sys.argv[1]
X, Y, W, H = [int(v) for v in sys.argv[2:6]]
try:
    img = Image.open(png).convert("L")
    w, h = img.size
    X, Y = max(0, X), max(0, Y)
    W = min(W, w - X)
    H = min(H, h - Y)
    if W <= 2 or H <= 2:
        print("SCORE=")
        sys.exit(0)
    img = img.crop((X, Y, X + W, Y + H))
    img = img.resize((W * 5, H * 5), Image.LANCZOS)
    img = img.point(lambda p: 0 if p < 150 else 255)
    txt = pytesseract.image_to_string(img, config="--psm 7 -c tessedit_char_whitelist=0123456789")
    print("SCORE=" + txt.strip())
except Exception as e:
    print("SCORE=")