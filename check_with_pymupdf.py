"""Check PDF with PyMuPDF"""
import fitz  # PyMuPDF

pdf_path = "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"

print("Checking PDF with PyMuPDF...")
doc = fitz.open(pdf_path)

print(f"Total pages: {len(doc)}")
print("\nFirst 10 pages text extraction:")

for page_num in range(min(10, len(doc))):
    page = doc[page_num]
    text = page.get_text("text")
    
    print(f"\n{'='*70}")
    print(f"PAGE {page_num + 1} - {len(text)} characters")
    print('='*70)
    
    if text.strip():
        lines = [l for l in text.split('\n') if l.strip()][:20]
        for i, line in enumerate(lines, 1):
            print(f"{i:3}. {line[:75]}")
    else:
        print("(No text - might be image-based)")

doc.close()
