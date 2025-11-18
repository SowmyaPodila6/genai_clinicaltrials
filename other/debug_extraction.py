"""
Debug script to test PDF extraction and see why summaries are empty
"""

import os
import sys
from langgraph_custom.langgraph_workflow import build_workflow

def test_pdf_extraction(pdf_path):
    """Test PDF extraction with full debugging"""
    print("=" * 80)
    print(f"Testing PDF: {pdf_path}")
    print("=" * 80)
    print()
    
    # Build workflow
    print("Building workflow...")
    workflow = build_workflow()
    print("✅ Workflow built")
    print()
    
    # Create initial state
    initial_state = {
        "input_url": pdf_path,
        "input_type": "unknown",
        "raw_data": {},
        "parsed_json": {},
        "data_to_summarize": {},
        "confidence_score": 0.0,
        "completeness_score": 0.0,
        "missing_fields": [],
        "nct_id": "",
        "chat_query": "generate_summary",
        "chat_response": "",
        "error": "",
        "used_llm_fallback": False
    }
    
    print("Running workflow...")
    print("-" * 80)
    
    # Run workflow
    result = workflow.invoke(initial_state)
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    # Print metrics
    print(f"Confidence Score: {result['confidence_score']:.2%}")
    print(f"Completeness Score: {result['completeness_score']:.2%}")
    print(f"Used LLM Fallback: {result['used_llm_fallback']}")
    print(f"Missing Fields: {result['missing_fields']}")
    print()
    
    # Print extracted data summary
    print("EXTRACTED DATA (parsed_json):")
    print("-" * 80)
    for field, value in result['parsed_json'].items():
        if value:
            word_count = len(str(value).split())
            preview = str(value)[:100].replace('\n', ' ')
            print(f"\n{field}:")
            print(f"  Words: {word_count}")
            print(f"  Preview: {preview}...")
        else:
            print(f"\n{field}: [EMPTY]")
    print()
    
    # Print data_to_summarize
    print("\nDATA TO SUMMARIZE (data_to_summarize):")
    print("-" * 80)
    for field, value in result['data_to_summarize'].items():
        if value:
            word_count = len(str(value).split())
            preview = str(value)[:100].replace('\n', ' ')
            print(f"\n{field}:")
            print(f"  Words: {word_count}")
            print(f"  Preview: {preview}...")
        else:
            print(f"\n{field}: [EMPTY]")
    print()
    
    # Print summary
    print("\nGENERATED SUMMARY:")
    print("-" * 80)
    if result['chat_response']:
        print(result['chat_response'])
    else:
        print("[NO SUMMARY GENERATED]")
    print()
    
    # Print errors if any
    if result.get('error'):
        print("\nERROR:")
        print("-" * 80)
        print(result['error'])
        print()
    
    return result


if __name__ == "__main__":
    # Test with your PDFs
    pdf_files = [
        "Prot_000.pdf",
        "HIV-HIV-2019-Venter-ADVANCE.pdf",
        "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"
    ]
    
    for pdf_file in pdf_files:
        if os.path.exists(pdf_file):
            print("\n" * 2)
            result = test_pdf_extraction(pdf_file)
            
            # Wait for user input before next PDF
            input("\n\nPress Enter to continue to next PDF...")
        else:
            print(f"❌ File not found: {pdf_file}")
