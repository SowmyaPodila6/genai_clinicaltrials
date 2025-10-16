"""
Example usage of the Clinical Trial PDF Parser
"""

from clinical_trail_parser import ClinicalTrialPDFParser
import os

def demonstrate_parser():
    """Demonstrate the PDF parser functionality."""
    
    # Initialize the parser
    parser = ClinicalTrialPDFParser()
    
    print("Clinical Trial PDF Parser - Example Usage")
    print("=" * 50)
    
    # Check if we have any PDF files in the current directory
    pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
    
    if pdf_files:
        print(f"Found PDF files: {pdf_files}")
        
        for pdf_file in pdf_files:
            print(f"\nParsing: {pdf_file}")
            print("-" * 30)
            
            try:
                # Parse the PDF
                sections = parser.parse_pdf_file(pdf_file)
                
                # Display section information
                print(f"Found {len(sections)} sections:")
                
                for section_name, content in sections.items():
                    word_count = len(content.split())
                    print(f"  • {section_name}: {word_count} words")
                    
                    # Show first 100 characters of content
                    preview = content[:100].replace('\n', ' ')
                    if len(content) > 100:
                        preview += "..."
                    print(f"    Preview: {preview}")
                    print()
                
                # Get section summary
                summary = parser.get_section_summary(sections)
                print(f"Total words by section: {summary}")
                
                # Example search
                search_term = "patient"
                search_results = parser.search_sections(sections, search_term)
                if search_results:
                    print(f"\nSentences containing '{search_term}':")
                    for section, sentences in search_results.items():
                        print(f"  {section}: {len(sentences)} matches")
                
            except Exception as e:
                print(f"Error parsing {pdf_file}: {e}")
    
    else:
        print("No PDF files found in the current directory.")
        print("\nTo test the parser:")
        print("1. Place a clinical trial PDF in this directory")
        print("2. Run this script again")
        print("\nAlternatively, you can use the parser programmatically:")
        print()
        print("Example code:")
        print("```python")
        print("from clinical_trail_parser import ClinicalTrialPDFParser")
        print("parser = ClinicalTrialPDFParser()")
        print("sections = parser.parse_pdf_file('your_file.pdf')")
        print("print(sections)")
        print("```")

def create_sample_usage():
    """Show how to use the parser with different input methods."""
    
    parser = ClinicalTrialPDFParser()
    
    print("\nSample Usage Methods:")
    print("=" * 30)
    
    # Method 1: From file path
    print("1. Parse from file path:")
    print("   sections = parser.parse_pdf_file('clinical_trial.pdf')")
    
    # Method 2: From bytes (useful for uploaded files)
    print("\n2. Parse from bytes (e.g., uploaded file):")
    print("   with open('clinical_trial.pdf', 'rb') as f:")
    print("       pdf_bytes = f.read()")
    print("   sections = parser.parse_pdf_bytes(pdf_bytes)")
    
    # Method 3: Search within sections
    print("\n3. Search within parsed sections:")
    print("   results = parser.search_sections(sections, 'methodology')")
    
    # Method 4: Get section summary
    print("\n4. Get section word counts:")
    print("   summary = parser.get_section_summary(sections)")

if __name__ == "__main__":
    demonstrate_parser()
    create_sample_usage()
