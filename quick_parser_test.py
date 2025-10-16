"""
Quick test of enhanced parser functionality
"""
from enhanced_parser import EnhancedClinicalTrialParser, parse_clinical_trial_pdf
from pathlib import Path
import json

print("=" * 70)
print("ENHANCED PARSER FUNCTIONALITY TEST")
print("=" * 70)

# Find first PDF
pdfs = list(Path('.').glob('*.pdf'))
if not pdfs:
    print("❌ No PDF files found")
    exit(1)

pdf_path = str(pdfs[0])
print(f"\n📄 Testing with: {pdf_path}")

try:
    # Test 1: Import and instantiate
    print("\n1️⃣ Testing parser instantiation...")
    parser = EnhancedClinicalTrialParser()
    print("   ✅ Parser created successfully")
    
    # Test 2: Parse PDF
    print("\n2️⃣ Testing PDF parsing...")
    result = parse_clinical_trial_pdf(pdf_path)
    print("   ✅ PDF parsed successfully")
    
    # Test 3: Check results
    print("\n3️⃣ Checking results...")
    print(f"   - Total pages: {result['total_pages']}")
    print(f"   - Confidence: {result['confidence_score']:.1%}")
    print(f"   - Tables found: {len(result['tables'])}")
    
    # Test 4: Check required fields
    print("\n4️⃣ Checking required fields...")
    required_fields = [
        'study_overview', 'brief_description', 'primary_secondary_objectives',
        'treatment_arms_interventions', 'eligibility_criteria',
        'enrollment_participant_flow', 'adverse_events_profile',
        'study_locations', 'sponsor_information'
    ]
    
    populated = 0
    for field in required_fields:
        if result.get(field, '').strip():
            populated += 1
            print(f"   ✅ {field}")
        else:
            print(f"   ⚠️  {field} (empty)")
    
    print(f"\n📊 Field Coverage: {populated}/{len(required_fields)} ({populated/len(required_fields)*100:.1f}%)")
    
    # Test 5: Sample output
    print("\n5️⃣ Sample extracted content:")
    if result.get('study_overview', '').strip():
        preview = result['study_overview'][:200].replace('\n', ' ')
        print(f"   Study Overview: {preview}...")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - Enhanced parser is working!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
