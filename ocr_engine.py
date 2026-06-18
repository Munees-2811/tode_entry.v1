import cv2
import numpy as np
from PIL import Image


def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return img, gray


def extract_text_tesseract(image_path, region=None):
    try:
        import pytesseract
    except ImportError:
        return "[pytesseract not installed]"

    img = Image.open(image_path)
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))

    text = pytesseract.image_to_string(img, config="--psm 6")
    return text.strip()


def extract_text_easyocr(image_path, region=None):
    try:
        import easyocr
    except ImportError:
        return "[easyocr not installed]"

    reader = easyocr.Reader(["en"], gpu=False)
    img = cv2.imread(image_path)
    if region:
        x, y, w, h = region
        img = img[y : y + h, x : x + w]

    results = reader.readtext(img)
    lines = [text for (_, text, conf) in results if conf > 0.3]
    return "\n".join(lines)


def extract_all_regions(image_path):
    img, gray = preprocess_image(image_path)
    contours, _ = cv2.findContours(
        cv2.bitwise_not(gray), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    regions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 50 and h > 15:
            regions.append((x, y, w, h))

    regions.sort(key=lambda r: (r[1], r[0]))
    return regions


def detect_fields(image_path):
    try:
        import pytesseract
    except ImportError:
        return []

    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    fields = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if text:
            fields.append(
                {
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "conf": int(data["conf"][i]),
                }
            )
    return fields
