import fitz, re
from typing import List, Dict

H_TAG = re.compile(r"^\s*[A-Z0-9].{0,60}$")

def detect_chunks(path: str) -> List[Dict]:
    pdf = fitz.open(path)
    chunks, current = [], None
    for page_num in range(pdf.page_count):
        text = pdf.load_page(page_num).get_text("text")
        for line in text.splitlines():
            if H_TAG.match(line.strip()):
                if current: chunks.append(current)
                current = {"header": line.strip(),
                           "body": "", "page": page_num + 1}
            elif current: # Ensure 'current' is not None before trying to add to its body
                current["body"] += line + " "
    if current: chunks.append(current)
    return chunks
