import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance


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


def preprocess_handwriting(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

    return img, gray


def preprocess_handwriting_pil(image_path, region=None):
    img = Image.open(image_path)
    if region:
        x, y, w, h = region
        img = img.crop((x, y, x + w, y + h))

    img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.point(lambda p: 255 if p > 140 else 0)

    return img


def extract_text_tesseract(image_path, region=None, handwriting=False):
    try:
        import pytesseract
    except ImportError:
        return "[pytesseract not installed]"

    if handwriting:
        img = preprocess_handwriting_pil(image_path, region)
        config = "--psm 6 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?@#$%&*()-+=/ "
    else:
        img = Image.open(image_path)
        if region:
            x, y, w, h = region
            img = img.crop((x, y, x + w, y + h))
        config = "--psm 6"

    text = pytesseract.image_to_string(img, config=config)
    return text.strip()


def extract_text_easyocr(image_path, region=None, handwriting=False):
    try:
        import easyocr
    except ImportError:
        return "[easyocr not installed]"

    reader = easyocr.Reader(["en"], gpu=False)

    if handwriting:
        _, processed = preprocess_handwriting(image_path)
        if region:
            x, y, w, h = region
            processed = processed[y : y + h, x : x + w]
        results = reader.readtext(processed)
        lines = [text for (_, text, conf) in results if conf > 0.2]
    else:
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


def detect_fields(image_path, handwriting=False):
    try:
        import pytesseract
    except ImportError:
        return []

    if handwriting:
        img = preprocess_handwriting_pil(image_path)
    else:
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


def smart_parse_lines(raw_text):
    parsed = {}
    lines = raw_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for sep in [":", "=", "-"]:
            if sep in line:
                parts = line.split(sep, 1)
                key = parts[0].strip()
                val = parts[1].strip()
                if key and val and len(key) < 40:
                    parsed[key] = val
                    break
    return parsed
