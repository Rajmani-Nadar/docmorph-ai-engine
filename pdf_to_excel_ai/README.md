# PDF to Excel AI

## What the project does

This project extracts handwritten student records from a PDF and exports them to Excel with the help of Google Gemini Vision AI.

## Features

- Reads a PDF and converts every page to 300 DPI images with pdf2image and Poppler
- Sends each page to Gemini Vision using the latest google-genai SDK with a Gemini model such as gemini-3.5-flash
- Cleans and validates the JSON response before saving records
- Writes a formatted Excel workbook with bold headers, frozen pane, autofilter, wrapping, and auto-sized columns
- Logs progress to logs/app.log

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.10+
- Poppler installed and available on PATH or configured through POPPLER_PATH
- Tesseract OCR installed locally and available on PATH
- A Google Gemini API key

## How to get a Gemini API key

1. Go to Google AI Studio: https://aistudio.google.com/
2. Sign in with your Google account
3. Create a new API key
4. Copy the key safely and store it in your .env file

## How to install Poppler

- Download Poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases
- Extract it and make sure the bin folder is available on PATH
- If you do not want to add it to PATH, set POPPLER_PATH in your .env file to the bin folder

## How to run the project

1. Install the required local tools:
   - Poppler
   - Tesseract OCR for Windows

2. Create your environment file:

```bash
copy .env.example .env
```

3. Edit .env and set your values:
   - GEMINI_API_KEY=your_key_here
   - PDF_FILE=path/to/your/input.pdf
   - OUTPUT_EXCEL=path/to/your/output.xlsx
   - POPPLER_PATH=path/to/poppler/bin (optional if Poppler is already on PATH)
   - MODEL_NAME=gemini-3.5-flash

4. Run the script:

```bash
python extract_to_excel.py
```

## Example output

The generated workbook will be saved at the location specified in OUTPUT_EXCEL.

## Configuration

The project reads these values from .env or falls back to defaults in config.py:

- GEMINI_API_KEY: your Gemini API key
- PDF_FILE: the input PDF file to process
- OUTPUT_EXCEL: the Excel file to create
- POPPLER_PATH: optional Poppler installation path
- MODEL_NAME: Gemini model name

## Notes

- Keep your .env file private and do not commit it to Git
- Use .env.example as the template for new environments
- You can replace the sample PDF and Excel names with your own file paths when needed
