"""
Example Usage of Enhanced Clinical Trial Parser
================================================

This script demonstrates how to use the enhanced parser with real PDFs.
"""

import sys
import json
from pathlib import Path
from enhanced_parser import EnhancedClinicalTrialParser, parse_clinical_trial_pdf


def example_basic_usage():
    """Example 1: Basic usage with convenience function."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 70)
    
    # Find a PDF in current directory
    pdfs = list(Path('.').glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found in current directory.")
        return
    
    pdf_path = str(pdfs[0])
    print(f"\nParsing: {pdf_path}")
    
    # Parse with one line
    result = parse_clinical_trial_pdf(pdf_path)
    
    # Display results
    print(f"\n✅ Parsing complete!")
    print(f"   Confidence Score: {result['confidence_score']:.2%}")
    print(f"   Total Pages: {result['total_pages']}")
    print(f"   Tables Found: {len(result['tables'])}")
    
    print("\n📋 Extracted Fields:")
    fields = [
        'study_overview', 'brief_description', 'primary_secondary_objectives',
        'treatment_arms_interventions', 'eligibility_criteria',
        'enrollment_participant_flow', 'adverse_events_profile',
        'study_locations', 'sponsor_information'
    ]
    
    for field in fields:
        value = result[field]
        status = "✓" if value.strip() else "✗"
        preview = (value[:60] + "...") if len(value) > 60 else value
        print(f"   {status} {field}: {preview or '(empty)'}")


def example_advanced_usage():
    """Example 2: Advanced usage with custom options."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Advanced Usage with Custom Options")
    print("=" * 70)
    
    pdfs = list(Path('.').glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found in current directory.")
        return
    
    pdf_path = str(pdfs[0])
    print(f"\nParsing: {pdf_path}")
    
    # Create parser with options
    parser = EnhancedClinicalTrialParser(
        use_ocr=False,  # Set to True if PDFs are scanned
        use_nlp=False   # Set to True for better section detection
    )
    
    # Parse PDF
    clinical_data, tables = parser.parse_pdf(pdf_path, extract_tables=True)
    
    # Display section-by-section results
    print("\n📄 Extracted Data by Field:")
    print("-" * 70)
    
    print(f"\n1. Study Overview ({len(clinical_data.study_overview)} chars):")
    print(f"   {clinical_data.study_overview[:150]}...")
    
    print(f"\n2. Objectives ({len(clinical_data.primary_secondary_objectives)} chars):")
    print(f"   {clinical_data.primary_secondary_objectives[:150]}...")
    
    print(f"\n3. Eligibility ({len(clinical_data.eligibility_criteria)} chars):")
    print(f"   {clinical_data.eligibility_criteria[:150]}...")
    
    # Display table information
    if tables:
        print(f"\n📊 Tables Extracted: {len(tables)}")
        for i, table in enumerate(tables, 1):
            print(f"\n   Table {i}:")
            print(f"   - Page: {table.page}")
            print(f"   - Size: {table.rows}×{table.columns}")
            print(f"   - Confidence: {table.confidence:.2%}")
            if table.title:
                print(f"   - Title: {table.title}")


def example_export_to_json():
    """Example 3: Export results to JSON."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Export to JSON")
    print("=" * 70)
    
    pdfs = list(Path('.').glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found in current directory.")
        return
    
    pdf_path = str(pdfs[0])
    output_path = f"parsed_{Path(pdf_path).stem}.json"
    
    print(f"\nParsing: {pdf_path}")
    print(f"Output: {output_path}")
    
    # Parse and export
    result = parse_clinical_trial_pdf(pdf_path, output_path=output_path)
    
    print(f"\n✅ Exported to: {output_path}")
    
    # Display JSON preview
    with open(output_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📄 JSON Preview (first 500 chars):")
    print(json.dumps(data, indent=2)[:500] + "...")


def example_batch_processing():
    """Example 4: Batch process multiple PDFs."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Batch Processing")
    print("=" * 70)
    
    pdfs = list(Path('.').glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found in current directory.")
        return
    
    print(f"\nFound {len(pdfs)} PDF files")
    
    # Create parser once for efficiency
    parser = EnhancedClinicalTrialParser()
    
    results = []
    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] Processing: {pdf.name}")
        
        try:
            clinical_data, tables = parser.parse_pdf(str(pdf))
            
            results.append({
                'file': pdf.name,
                'status': 'success',
                'confidence': clinical_data.confidence_score,
                'pages': clinical_data.total_pages,
                'tables': len(tables)
            })
            
            print(f"   ✓ Success (confidence: {clinical_data.confidence_score:.2%})")
            
        except Exception as e:
            results.append({
                'file': pdf.name,
                'status': 'failed',
                'error': str(e)
            })
            print(f"   ✗ Failed: {str(e)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 70)
    
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - successful
    
    print(f"\nTotal: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    if successful > 0:
        avg_confidence = sum(r['confidence'] for r in results if r['status'] == 'success') / successful
        print(f"Average Confidence: {avg_confidence:.2%}")


def example_section_inspection():
    """Example 5: Inspect detected sections before mapping."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Section Inspection")
    print("=" * 70)
    
    pdfs = list(Path('.').glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found in current directory.")
        return
    
    pdf_path = str(pdfs[0])
    print(f"\nAnalyzing: {pdf_path}")
    
    parser = EnhancedClinicalTrialParser()
    
    # Step 1: Extract text
    print("\n1️⃣ Extracting text...")
    text, metadata = parser.extract_text_multimethod(pdf_path)
    print(f"   Method: {metadata['method']}")
    print(f"   Pages: {metadata['pages']}")
    print(f"   Characters: {len(text)}")
    
    # Step 2: Detect sections
    print("\n2️⃣ Detecting sections...")
    sections = parser.detect_sections_advanced(text)
    print(f"   Sections found: {len(sections)}")
    
    # Display detected sections
    print("\n📑 Detected Sections:")
    for i, section in enumerate(sections[:15], 1):  # Show first 15
        print(f"   {i}. {section.title}")
        print(f"      Level: {section.level}, Confidence: {section.confidence:.2%}")
    
    if len(sections) > 15:
        print(f"   ... and {len(sections) - 15} more sections")
    
    # Step 3: Extract content
    print("\n3️⃣ Extracting section content...")
    content = parser.extract_section_content(text, sections)
    
    print(f"\n📝 Sample Section Content:")
    for title, text in list(content.items())[:3]:
        print(f"\n   Section: {title}")
        print(f"   Length: {len(text)} characters")
        print(f"   Preview: {text[:100]}...")


def main():
    """Run all examples or specific example."""
    examples = {
        '1': ('Basic Usage', example_basic_usage),
        '2': ('Advanced Usage', example_advanced_usage),
        '3': ('Export to JSON', example_export_to_json),
        '4': ('Batch Processing', example_batch_processing),
        '5': ('Section Inspection', example_section_inspection),
    }
    
    if len(sys.argv) > 1:
        # Run specific example
        example_num = sys.argv[1]
        if example_num in examples:
            print(f"\nRunning: {examples[example_num][0]}")
            examples[example_num][1]()
        else:
            print(f"Unknown example: {example_num}")
            print(f"Available examples: {', '.join(examples.keys())}")
    else:
        # Run all examples
        print("\n" + "=" * 70)
        print("ENHANCED CLINICAL TRIAL PARSER - EXAMPLES")
        print("=" * 70)
        
        for num, (name, func) in examples.items():
            try:
                func()
            except Exception as e:
                print(f"\n❌ Example {num} failed: {str(e)}")
        
        print("\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETE")
        print("=" * 70)
        print("\nTo run a specific example:")
        for num, (name, _) in examples.items():
            print(f"  python examples_enhanced_parser.py {num}  # {name}")


if __name__ == '__main__':
    main()
