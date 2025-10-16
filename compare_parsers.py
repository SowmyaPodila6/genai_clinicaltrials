"""
Comparison Script: Basic vs Enhanced Parser
============================================

This script compares the performance and accuracy of the basic parser
vs the enhanced parser on the same PDFs.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any

# Import both parsers
from clinical_trail_parser import ClinicalTrialPDFParser as BasicParser
from enhanced_parser import EnhancedClinicalTrialParser as EnhancedParser


def measure_performance(parser_func, pdf_path: str) -> Dict[str, Any]:
    """Measure parsing performance."""
    start_time = time.time()
    
    try:
        result = parser_func(pdf_path)
        duration = time.time() - start_time
        
        return {
            'success': True,
            'duration': duration,
            'result': result,
            'error': None
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            'success': False,
            'duration': duration,
            'result': None,
            'error': str(e)
        }


def count_populated_fields(data: Dict[str, str]) -> int:
    """Count how many fields have meaningful content."""
    required_fields = [
        'Study Overview', 'Brief Description', 'Primary and Secondary Objectives',
        'Treatment Arms and Interventions', 'Eligibility Criteria',
        'Enrollment and Participant Flow', 'Adverse Events Profile',
        'Study Locations', 'Sponsor Information'
    ]
    
    # Handle different key formats
    count = 0
    for field in required_fields:
        # Try original format
        value = data.get(field, '')
        # Try snake_case format
        if not value:
            snake_case = field.lower().replace(' ', '_').replace('and_', '')
            value = data.get(snake_case, '')
        
        if value and len(str(value).strip()) > 20:  # At least 20 chars of content
            count += 1
    
    return count


def parse_with_basic(pdf_path: str) -> Dict:
    """Parse with basic parser."""
    parser = BasicParser()
    sections = parser.parse_pdf_file(pdf_path)
    
    # Map to schema
    from clinical_trail_parser import map_sections_to_schema
    result = map_sections_to_schema(sections)
    
    return result


def parse_with_enhanced(pdf_path: str) -> Dict:
    """Parse with enhanced parser."""
    from enhanced_parser import parse_clinical_trial_pdf
    result = parse_clinical_trial_pdf(pdf_path)
    return result


def compare_parsers(pdf_path: str):
    """Compare both parsers on a single PDF."""
    print("=" * 80)
    print(f"COMPARING PARSERS ON: {Path(pdf_path).name}")
    print("=" * 80)
    
    # Test Basic Parser
    print("\n📘 BASIC PARSER")
    print("-" * 80)
    basic_result = measure_performance(parse_with_basic, pdf_path)
    
    if basic_result['success']:
        print(f"✓ Success")
        print(f"  Duration: {basic_result['duration']:.2f} seconds")
        
        populated = count_populated_fields(basic_result['result'])
        print(f"  Populated fields: {populated}/9")
        
        # Show sample field
        overview = basic_result['result'].get('Study Overview', '')
        print(f"  Sample (Study Overview): {overview[:100]}...")
    else:
        print(f"✗ Failed: {basic_result['error']}")
        print(f"  Duration: {basic_result['duration']:.2f} seconds")
    
    # Test Enhanced Parser
    print("\n📗 ENHANCED PARSER")
    print("-" * 80)
    enhanced_result = measure_performance(parse_with_enhanced, pdf_path)
    
    if enhanced_result['success']:
        print(f"✓ Success")
        print(f"  Duration: {enhanced_result['duration']:.2f} seconds")
        
        populated = count_populated_fields(enhanced_result['result'])
        print(f"  Populated fields: {populated}/9")
        print(f"  Confidence score: {enhanced_result['result'].get('confidence_score', 0):.2%}")
        
        # Show sample field
        overview = enhanced_result['result'].get('study_overview', '')
        print(f"  Sample (Study Overview): {overview[:100]}...")
    else:
        print(f"✗ Failed: {enhanced_result['error']}")
        print(f"  Duration: {enhanced_result['duration']:.2f} seconds")
    
    # Comparison Summary
    print("\n📊 COMPARISON SUMMARY")
    print("-" * 80)
    
    if basic_result['success'] and enhanced_result['success']:
        basic_populated = count_populated_fields(basic_result['result'])
        enhanced_populated = count_populated_fields(enhanced_result['result'])
        
        print(f"Field Completeness:")
        print(f"  Basic:    {basic_populated}/9 ({basic_populated/9*100:.1f}%)")
        print(f"  Enhanced: {enhanced_populated}/9 ({enhanced_populated/9*100:.1f}%)")
        
        if enhanced_populated > basic_populated:
            improvement = enhanced_populated - basic_populated
            print(f"  → Enhanced found {improvement} more fields! 📈")
        elif enhanced_populated == basic_populated:
            print(f"  → Same field count ⚖️")
        else:
            print(f"  → Basic found more fields ⚠️")
        
        print(f"\nProcessing Time:")
        print(f"  Basic:    {basic_result['duration']:.2f}s")
        print(f"  Enhanced: {enhanced_result['duration']:.2f}s")
        
        if enhanced_result['duration'] < basic_result['duration']:
            print(f"  → Enhanced is faster! ⚡")
        elif enhanced_result['duration'] < basic_result['duration'] * 1.5:
            print(f"  → Similar speed ⚖️")
        else:
            print(f"  → Basic is faster ⚠️")
        
        # Content quality comparison
        print(f"\nContent Quality:")
        basic_total_chars = sum(len(str(v)) for v in basic_result['result'].values())
        enhanced_total_chars = sum(len(str(v)) for v in enhanced_result['result'].values())
        
        print(f"  Basic:    {basic_total_chars:,} characters")
        print(f"  Enhanced: {enhanced_total_chars:,} characters")
        
        if enhanced_total_chars > basic_total_chars * 1.2:
            print(f"  → Enhanced extracted significantly more content! 📚")
        elif enhanced_total_chars > basic_total_chars:
            print(f"  → Enhanced extracted more content 📖")
        else:
            print(f"  → Similar content volume")
    
    return basic_result, enhanced_result


def batch_comparison(pdf_folder: str = '.'):
    """Compare parsers on all PDFs in a folder."""
    pdfs = list(Path(pdf_folder).glob('*.pdf'))
    
    if not pdfs:
        print("No PDF files found!")
        return
    
    print("=" * 80)
    print(f"BATCH COMPARISON - {len(pdfs)} PDF FILES")
    print("=" * 80)
    
    results = []
    
    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] Processing: {pdf.name}")
        print("=" * 80)
        
        basic_result, enhanced_result = compare_parsers(str(pdf))
        
        results.append({
            'file': pdf.name,
            'basic': basic_result,
            'enhanced': enhanced_result
        })
    
    # Overall Summary
    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    
    basic_successes = sum(1 for r in results if r['basic']['success'])
    enhanced_successes = sum(1 for r in results if r['enhanced']['success'])
    
    print(f"\nSuccess Rate:")
    print(f"  Basic:    {basic_successes}/{len(pdfs)} ({basic_successes/len(pdfs)*100:.1f}%)")
    print(f"  Enhanced: {enhanced_successes}/{len(pdfs)} ({enhanced_successes/len(pdfs)*100:.1f}%)")
    
    if enhanced_successes >= basic_successes:
        print(f"  → Enhanced is more reliable! ✅")
    
    # Average metrics for successful parses
    if basic_successes > 0:
        avg_basic_time = sum(r['basic']['duration'] for r in results if r['basic']['success']) / basic_successes
        avg_basic_fields = sum(
            count_populated_fields(r['basic']['result']) 
            for r in results if r['basic']['success']
        ) / basic_successes
        
        print(f"\nBasic Parser Averages:")
        print(f"  Time: {avg_basic_time:.2f}s")
        print(f"  Populated fields: {avg_basic_fields:.1f}/9")
    
    if enhanced_successes > 0:
        avg_enhanced_time = sum(r['enhanced']['duration'] for r in results if r['enhanced']['success']) / enhanced_successes
        avg_enhanced_fields = sum(
            count_populated_fields(r['enhanced']['result']) 
            for r in results if r['enhanced']['success']
        ) / enhanced_successes
        avg_confidence = sum(
            r['enhanced']['result'].get('confidence_score', 0) 
            for r in results if r['enhanced']['success']
        ) / enhanced_successes
        
        print(f"\nEnhanced Parser Averages:")
        print(f"  Time: {avg_enhanced_time:.2f}s")
        print(f"  Populated fields: {avg_enhanced_fields:.1f}/9")
        print(f"  Confidence: {avg_confidence:.2%}")
    
    if basic_successes > 0 and enhanced_successes > 0:
        field_improvement = ((avg_enhanced_fields - avg_basic_fields) / avg_basic_fields) * 100
        print(f"\n🎯 IMPROVEMENT: {field_improvement:+.1f}% more fields populated!")
        
        if avg_confidence > 0.8:
            print(f"🎯 HIGH CONFIDENCE: {avg_confidence:.1%} average confidence score!")


def detailed_field_comparison(pdf_path: str):
    """Show detailed field-by-field comparison."""
    print("=" * 80)
    print(f"DETAILED FIELD COMPARISON: {Path(pdf_path).name}")
    print("=" * 80)
    
    # Parse with both
    basic_result = parse_with_basic(pdf_path)
    enhanced_result = parse_with_enhanced(pdf_path)
    
    fields = [
        'Study Overview', 'Brief Description', 'Primary and Secondary Objectives',
        'Treatment Arms and Interventions', 'Eligibility Criteria',
        'Enrollment and Participant Flow', 'Adverse Events Profile',
        'Study Locations', 'Sponsor Information'
    ]
    
    for field in fields:
        print(f"\n{'─' * 80}")
        print(f"📋 {field}")
        print('─' * 80)
        
        # Get values (handle different formats)
        basic_value = basic_result.get(field, '')
        enhanced_value = enhanced_result.get(field.lower().replace(' ', '_').replace('and_', ''), '')
        
        print(f"\nBasic Parser ({len(basic_value)} chars):")
        if basic_value:
            print(f"  {basic_value[:200]}...")
        else:
            print("  (empty)")
        
        print(f"\nEnhanced Parser ({len(enhanced_value)} chars):")
        if enhanced_value:
            print(f"  {enhanced_value[:200]}...")
        else:
            print("  (empty)")
        
        # Comparison
        if len(enhanced_value) > len(basic_value):
            print(f"\n✓ Enhanced has {len(enhanced_value) - len(basic_value)} more characters")
        elif len(enhanced_value) < len(basic_value):
            print(f"\n⚠ Basic has {len(basic_value) - len(enhanced_value)} more characters")
        else:
            print(f"\n⚖ Same length")


def main():
    """Main comparison script."""
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == 'single' and len(sys.argv) > 2:
            # Compare single PDF
            compare_parsers(sys.argv[2])
        
        elif mode == 'batch':
            # Batch comparison
            batch_comparison()
        
        elif mode == 'detailed' and len(sys.argv) > 2:
            # Detailed field comparison
            detailed_field_comparison(sys.argv[2])
        
        else:
            print("Usage:")
            print("  python compare_parsers.py single <pdf_file>")
            print("  python compare_parsers.py batch")
            print("  python compare_parsers.py detailed <pdf_file>")
    else:
        # Default: batch comparison
        batch_comparison()


if __name__ == '__main__':
    main()
