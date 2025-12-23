import os
import logging
from pypdf import PdfReader

def parse_resume(file_path: str) -> str:
    """
    Reads a PDF file from the given path and extracts the text.
    Returns an empty string if the file cannot be read.
    """
    # 1. Validation: Check if path exists
    if not file_path or not os.path.exists(file_path):
        logging.warning(f"Resume parsing skipped. File not found at: {file_path}")
        return ""

    # Initialize variable OUTSIDE the try block to prevent UnboundLocalError
    full_text = ""

    try:
        # 2. Open the PDF
        reader = PdfReader(file_path)
        
        # 3. Extract text from all pages
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # 4. Clean up text
        cleaned_text = " ".join(full_text.split())
        
        logging.info(f"✅ Successfully parsed resume ({len(cleaned_text)} characters)")
        return cleaned_text

    except Exception as e:
        # If parsing fails, we log it but return empty string so the Agent doesn't crash
        logging.error(f"❌ Error reading PDF: {e}")
        return ""