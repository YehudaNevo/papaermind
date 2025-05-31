# papermind/tests/create_dummy.py
import os
import fitz # PyMuPDF

def create_dummy_pdf_for_testing(pdf_dir: str = "papermind/data/pdfs", pdf_name: str = "dummy.pdf") -> str:
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_name)
    if not os.path.exists(pdf_path):
        try:
            doc = fitz.open() # Create a new empty PDF document
            page = doc.new_page()

            # Add some hierarchical content
            page.insert_text((72, 72), "PaperMind Test Document", fontsize=18, fontname="helvB") # Title

            page.insert_text((72, 108), "CHAPTER 1: The Beginning", fontsize=16, fontname="helvB")
            page.insert_text((72, 128), "This is the first paragraph of the first chapter. It contains introductory material.", fontsize=11, fontname="helv")
            page.insert_text((72, 148), "Section 1.1: Early Concepts", fontsize=14, fontname="helvB")
            page.insert_text((72, 164), "Exploring the initial ideas and theories related to the subject.", fontsize=10, fontname="helv")

            page.insert_text((72, 200), "CHAPTER 2: Advanced Topics", fontsize=16, fontname="helvB")
            page.insert_text((72, 220), "This chapter delves into more complex subjects, building upon the foundations.", fontsize=11, fontname="helv")
            page.insert_text((72, 240), "Section 2.1: Deep Dive", fontsize=14, fontname="helvB")
            page.insert_text((72, 256), "A thorough examination of intricate details and advanced methodologies.", fontsize=10, fontname="helv")

            doc.save(pdf_path)
            print(f"Created dummy PDF: {pdf_path}")
            return pdf_path
        except Exception as e:
            print(f"Could not create dummy PDF with PyMuPDF (fitz): {e}")
            # Fallback to a simple text file if PyMuPDF fails for any reason
            txt_fallback_path = os.path.join(pdf_dir, "dummy_fallback.txt")
            with open(txt_fallback_path, "w") as f:
                f.write("CHAPTER 1: The Beginning\nThis is a test paragraph for fallback.\n")
                f.write("Section 1.1: Early Concepts\nFallback concepts here.\n")
            print(f"Created dummy text file as fallback: {txt_fallback_path}")
            return txt_fallback_path # Return .txt path
    return pdf_path
