"""Extract just first 5 pages of text to see PDF structure"""
import pdfplumber

pdf_path = "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"

print("Extracting first 5 pages...")
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages[:5]):
        print(f"\n{'='*70}")
        print(f"PAGE {i+1}")
        print('='*70)
        text = page.extract_text()
        if text:
            lines = text.split('\n')
            for j, line in enumerate(lines[:30], 1):  # First 30 lines per page
                if line.strip():
                    print(f"{j:3}. {line}")
        else:
            print("(No text extracted)")

print("\n" + "="*70)
print("DONE - Check if you see section headers above")
print("="*70)
