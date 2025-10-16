"""
Quick diagnostic - check why fields are empty
"""
from enhanced_parser import EnhancedClinicalTrialParser
import sys

print("=" * 70)
print("QUICK DIAGNOSTIC TEST")
print("=" * 70)

# Test with first PDF
pdf_path = "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"
print(f"\nTesting: {pdf_path}\n")

try:
    parser = EnhancedClinicalTrialParser()
    
    # Step 1: Extract text
    print("Step 1: Extracting text...")
    text = parser.extract_text_multimethod(pdf_path)
    print(f"✅ Extracted {len(text)} characters")
    print(f"   Preview: {text[:200]}...")
    
    # Step 2: Detect sections
    print("\nStep 2: Detecting sections...")
    sections = parser.detect_sections_advanced(text, pdf_path)
    print(f"✅ Detected {len(sections)} sections")
    
    if sections:
        print("\n   First 5 sections:")
        for i, section in enumerate(sections[:5], 1):
            title = section.get('title', 'N/A')[:50]
            content_len = len(section.get('content', ''))
            print(f"   {i}. '{title}' ({content_len} chars)")
    else:
        print("   ⚠️  WARNING: No sections detected!")
        print("   This means section headers weren't found in the PDF")
    
    # Step 3: Map to schema
    print("\nStep 3: Mapping to schema...")
    mapped = parser.map_to_clinical_trial_schema(sections)
    
    print(f"\n✅ Schema mapping complete")
    print("\nField mapping results:")
    
    fields = [
        'study_overview', 'brief_description', 'primary_secondary_objectives',
        'treatment_arms_interventions', 'eligibility_criteria',
        'enrollment_participant_flow', 'adverse_events_profile',
        'study_locations', 'sponsor_information'
    ]
    
    for field in fields:
        value = mapped.get(field, '')
        status = "✅" if value.strip() else "❌"
        print(f"{status} {field}: {len(value)} chars")
        
        # Show why it's empty
        if not value.strip():
            print(f"   → Field is empty - no matching section found")
    
    # Step 4: Check if the problem is in section detection
    print("\n" + "=" * 70)
    print("DIAGNOSIS:")
    print("=" * 70)
    
    if not sections:
        print("❌ PROBLEM: No sections detected from PDF")
        print("   Possible causes:")
        print("   1. PDF has no clear section headers")
        print("   2. Section patterns don't match PDF format")
        print("   3. Text extraction failed")
        print("\n   Recommendation: Check PDF structure manually")
    elif len(sections) < 5:
        print("⚠️  WARNING: Very few sections detected")
        print(f"   Only {len(sections)} sections found")
        print("   PDF may have non-standard formatting")
    else:
        # Check mapping success
        populated = sum(1 for f in fields if mapped.get(f, '').strip())
        if populated == 0:
            print("❌ PROBLEM: Sections detected but not mapped to schema")
            print("   Possible causes:")
            print("   1. Section titles don't match schema field patterns")
            print("   2. Fuzzy matching threshold too strict")
            print("\n   Section titles in PDF:")
            for section in sections[:10]:
                print(f"   - {section.get('title', 'N/A')[:60]}")
        else:
            print(f"✅ SUCCESS: {populated}/{len(fields)} fields populated")
    
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
