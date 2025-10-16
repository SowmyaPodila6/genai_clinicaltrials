"""
Test script to demonstrate PDF parsing functionality
"""

from clinical_trail_parser import ClinicalTrialPDFParser
import io

def test_parser_with_sample_text():
    """Test the parser with sample clinical trial text."""
    
    # Sample clinical trial text with headers on separate lines
    sample_text = """
ABSTRACT

This is a Phase II randomized controlled trial to evaluate the efficacy of Drug X 
in patients with advanced cancer. The primary endpoint is overall survival.

INTRODUCTION

Cancer remains a leading cause of death worldwide. Novel treatments are needed 
to improve patient outcomes and quality of life.

METHODS

This study will recruit 200 patients from multiple centers. Patients will be 
randomized to receive either Drug X or placebo.

Study Design

This is a double-blind, placebo-controlled trial.

RESULTS

The primary analysis will be conducted when 150 events have occurred.

DISCUSSION

The results of this study will inform future treatment guidelines.

CONCLUSIONS

Drug X shows promise as a new treatment option for advanced cancer patients.

REFERENCES

1. Smith J et al. Cancer treatment advances. J Cancer Res. 2023.
2. Jones A et al. Novel drug development. Med Oncol. 2022.
"""

    print("Testing Clinical Trial PDF Parser")
    print("=" * 50)
    
    # Initialize parser
    parser = ClinicalTrialPDFParser()
    
    # Debug: Show what lines look like
    lines = sample_text.split('\n')
    print("Sample lines for debugging:")
    for i, line in enumerate(lines[:15]):
        print(f"Line {i}: '{line.strip()}'")
    
    # Test header identification
    headers = parser.identify_section_headers(sample_text)
    print(f"\nIdentified headers: {headers}")
    
    # Parse the sample text
    sections = parser.parse_by_sections(sample_text)
    
    print(f"\nFound {len(sections)} sections:")
    print("-" * 30)
    
    for section_name, content in sections.items():
        word_count = len(content.split())
        print(f"\n📋 {section_name}")
        print(f"   Words: {word_count}")
        print(f"   Preview: {content[:100]}...")
    
    # Test section summary
    summary = parser.get_section_summary(sections)
    print(f"\n📊 Section Summary:")
    for section, words in summary.items():
        print(f"   {section}: {words} words")
    
    # Test search functionality
    search_results = parser.search_sections(sections, "patient", case_sensitive=False)
    print(f"\n🔍 Search results for 'patient':")
    for section, sentences in search_results.items():
        print(f"   {section}: {len(sentences)} matches")
        for sentence in sentences[:1]:  # Show first match
            print(f"     • {sentence.strip()}")
    
    print("\n✅ Parser test completed successfully!")
    return sections

if __name__ == "__main__":
    test_parser_with_sample_text()
