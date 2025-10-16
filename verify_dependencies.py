"""
Dependency Verification Script
===============================

Checks all dependencies for the Enhanced Clinical Trial Parser
"""

import sys

print("=" * 70)
print("DEPENDENCY VERIFICATION")
print("=" * 70)

dependencies = {
    "Core PDF Processing": [
        ("pdfplumber", "pdfplumber"),
        ("PyMuPDF (fitz)", "fitz"),
        ("pdfminer.six", "pdfminer.high_level"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
    ],
    "Existing App Dependencies": [
        ("streamlit", "streamlit"),
        ("openai", "openai"),
        ("requests", "requests"),
        ("python-docx", "docx"),
        ("PyPDF2", "PyPDF2"),
    ],
    "Optional - OCR Support": [
        ("Pillow", "PIL"),
        ("pytesseract", "pytesseract"),
    ],
    "Optional - NLP Support": [
        ("spacy", "spacy"),
    ],
}

all_installed = True
missing_deps = []
installed_deps = []

for category, deps in dependencies.items():
    print(f"\n{category}:")
    print("-" * 70)
    
    for display_name, import_name in deps:
        try:
            __import__(import_name)
            print(f"  ✅ {display_name}")
            installed_deps.append(display_name)
        except ImportError:
            print(f"  ❌ {display_name} - NOT INSTALLED")
            missing_deps.append((display_name, import_name))
            all_installed = False

# Check for spaCy language model if spaCy is installed
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
        print("  ✅ spaCy English model (en_core_web_sm)")
    except OSError:
        print("  ⚠️  spaCy English model - NOT DOWNLOADED")
        print("     Install with: python -m spacy download en_core_web_sm")
except ImportError:
    pass

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if all_installed:
    print("✅ ALL DEPENDENCIES INSTALLED!")
    print(f"   Total: {len(installed_deps)} packages")
else:
    print(f"⚠️  {len(missing_deps)} DEPENDENCIES MISSING")
    print("\nMissing packages:")
    for display_name, import_name in missing_deps:
        print(f"  - {display_name}")
    
    print("\nTo install missing dependencies:")
    package_names = [name for name, _ in missing_deps]
    print(f"  pip install {' '.join(package_names)}")

print("\n" + "=" * 70)
print("ENHANCED PARSER STATUS")
print("=" * 70)

# Check if enhanced parser can be imported
try:
    from enhanced_parser import EnhancedClinicalTrialParser
    print("✅ Enhanced parser module loaded successfully!")
    
    # Check which features are available
    parser = EnhancedClinicalTrialParser()
    print("\nFeatures available:")
    print(f"  • Multi-method text extraction: ✅")
    print(f"  • Section detection: ✅")
    print(f"  • Table extraction: ✅")
    print(f"  • Schema mapping: ✅")
    
    # Check optional features
    try:
        from PIL import Image
        import pytesseract
        print(f"  • OCR support: ✅ (requires Tesseract OCR engine)")
    except ImportError:
        print(f"  • OCR support: ❌ (install Pillow and pytesseract)")
    
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print(f"  • NLP enhancement: ✅")
    except:
        print(f"  • NLP enhancement: ❌ (install spacy and download model)")
    
    print("\n🚀 READY TO USE!")
    
except ImportError as e:
    print(f"❌ Cannot import enhanced parser: {e}")
    print("   Install missing dependencies first.")
    sys.exit(1)

print("=" * 70)
print("\nTo test the parser, run:")
print("  python quick_test.py")
print("  python examples_enhanced_parser.py")
print("=" * 70)
