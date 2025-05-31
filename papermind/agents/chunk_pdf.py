import fitz, re
from typing import List, Dict

H_TAG = re.compile(r"^\s*[A-Z0-9].{0,60}$")

def detect_chunks(path: str) -> List[Dict]:
    pdf = fitz.open(path)
    chunks, current = [], None
    prev_size = 10.0
    for i in range(pdf.page_count):
        page = pdf.load_page(i)
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                size = spans[0].get("size", 10.0)
                text = "".join(s.get("text", "") for s in spans).strip()
                header_by_size = size > prev_size * 1.15
                if H_TAG.match(text) and (header_by_size or len(text) < 60):
                    if current:
                        current["body"] = current["body"].strip()
                        chunks.append(current)
                    current = {"header": text, "body": "", "page": i + 1}
                elif current:
                    current["body"] += text + " "
                if text:
                    prev_size = size
            prev_size = 10.0
    if current:
        current["body"] = current["body"].strip()
        chunks.append(current)
    return chunks
