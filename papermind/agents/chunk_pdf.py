import fitz
import re
from typing import List, Dict

H_TAG = re.compile(r"^\s*[A-Z0-9].{0,60}$")

def detect_chunks(path: str) -> List[Dict]:
    pdf = fitz.open(path)
    chunks, current = [], None

    default_font_size = 10.0
    previous_line_font_size = default_font_size

    for page_num in range(pdf.page_count):
        page = pdf.load_page(page_num)
        page_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_LIGATURES & ~fitz.TEXT_PRESERVE_IMAGES)

        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:
                for line_dict in block.get("lines", []):
                    if not line_dict.get("spans"):
                        continue

                    first_span = line_dict["spans"][0]
                    current_line_font_size = first_span.get("size", default_font_size)
                    line_text_parts = [span.get("text", "") for span in line_dict["spans"]]
                    line_text = "".join(line_text_parts).strip()

                    is_potential_header_by_size = current_line_font_size > (previous_line_font_size * 1.15) # e.g. 15% larger

                    if H_TAG.match(line_text) and (is_potential_header_by_size or len(line_text) < 60) : # Shorter lines also candidates
                        if current:
                            if current["body"]:
                                current["body"] = current["body"].strip()
                            chunks.append(current)
                        current = {"header": line_text, "body": "", "page": page_num + 1}
                    elif current:
                        current["body"] += line_text + " "

                    if line_text: # Only update previous_line_font_size if the line was not empty
                        previous_line_font_size = current_line_font_size
                previous_line_font_size = default_font_size # Reset for new block or keep last from block? For now, reset.

    if current:
        if current["body"]:
            current["body"] = current["body"].strip()
        chunks.append(current)

    return chunks
