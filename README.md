# TODE Entry v1 — Computer Vision Data Entry Automation

A desktop tool that uses computer vision and OCR to extract text from images/documents and auto-fill data entry forms. Built with Tkinter for the UI and OpenCV + Tesseract/EasyOCR for text extraction.

## Features

- **Image Loading**: Load images, scanned documents, photos of forms
- **OCR Extraction**: Extract text using Tesseract or EasyOCR
- **Region Selection**: Draw bounding boxes to extract specific fields
- **Field Mapping**: Map extracted text to named data fields
- **Data Review**: Edit extracted data before export
- **Export**: Save to CSV/JSON

## Quick Start

```bash
# Install system dependency (Ubuntu/Debian)
sudo apt-get install tesseract-ocr

# Install Python packages
pip install -r requirements.txt

# Run
python main.py
```

## Stack

- **UI**: Tkinter
- **CV**: OpenCV, Pillow
- **OCR**: Tesseract, EasyOCR
- **Data**: Pandas
- **IDE**: PyCharm <> GitHub <> Claude Code
