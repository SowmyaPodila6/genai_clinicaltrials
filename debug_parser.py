"""
Debug version of parser test - shows what's happening internally
"""
from enhanced_parser import EnhancedClinicalTrialParser
import sys

pdf_path = "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"
parser = EnhancedClinicalTrialParser()

print("=" * 70)
print("DEBUGGING PARSER")
print("=" * 70)

# Step 1: Extract text
print("\n1. Extracting text...")
text, metadata = parser.extract_text_multimethod(pdf_path)
print(f"   ✅ Extracted {len(text):,} characters")
print(f"   Pages: {metadata['pages']}")
print(f"   Method: {metadata['method']}")
print(f"\n   First 500 chars of text:")
print(f"   {text[:500]}")

# Step 2: Detect sections
print("\n2. Detecting sections...")
sections = parser.detect_sections_advanced(text)
print(f"   Found {len(sections)} sections")

if sections:
    print("\n   First 10 sections:")
    for i, section in enumerate(sections[:10], 1):
        print(f"   {i}. {section.title[:60]} (confidence: {section.confidence:.2f})")
else:
    print("   ⚠️ NO SECTIONS DETECTED!")
    print("\n   Checking if patterns match...")
    
    # Check if any patterns match
    lines = text.split('\n')[:100]  # First 100 lines
    print(f"\n   First 20 lines of PDF:")
    for i, line in enumerate(lines[:20], 1):
        if line.strip():
            print(f"   {i:3}. {line.strip()[:70]}")
    
    # Check one pattern manually
    print("\n   Testing pattern matching on first 100 lines...")
    import re
    test_pattern = re.compile(r'^\d+\.?\s+[A-Z][A-Za-z\s]+', re.MULTILINE)
    for i, line in enumerate(lines[:100]):
        if test_pattern.match(line.strip()):
            print(f"   ✅ Line {i} matches: {line.strip()[:60]}")

# Step 3: Extract section content
print("\n3. Extracting section content...")
if sections:
    content_dict = parser.extract_section_content(text, sections)
    print(f"   Extracted content for {len(content_dict)} sections")
    
    # Show first section content
    if content_dict:
        first_key = list(content_dict.keys())[0]
        first_content = content_dict[first_key]
        print(f"\n   First section ({first_key}):")
        print(f"   {first_content[:200]}...")
else:
    print("   ⚠️ No sections to extract content from")
    content_dict = {}

# Step 4: Map to schema
print("\n4. Mapping to schema...")
tables = []
clinical_data = parser.map_to_clinical_trial_schema(content_dict, tables)

print(f"   Confidence: {clinical_data.confidence_score:.1%}")

fields = [
    'study_overview', 'brief_description', 'primary_secondary_objectives',
    'treatment_arms_interventions', 'eligibility_criteria',
    'enrollment_participant_flow', 'adverse_events_profile',
    'study_locations', 'sponsor_information'
]

populated = 0
for field in fields:
    value = getattr(clinical_data, field, '')
    if value.strip():
        populated += 1
        print(f"   ✅ {field}: {len(value)} chars")
    else:
        print(f"   ❌ {field}: empty")

print(f"\n   Coverage: {populated}/{len(fields)} ({populated/len(fields)*100:.0f}%)")

print("\n" + "=" * 70)
print("DIAGNOSIS:")
if len(sections) == 0:
    print("❌ ROOT CAUSE: No sections detected from PDF text")
    print("   This means the section patterns don't match the PDF's formatting")
elif len(content_dict) == 0:
    print("❌ ROOT CAUSE: Sections detected but content extraction failed")
elif populated == 0:
    print("❌ ROOT CAUSE: Content extracted but schema mapping failed")
    print("   Section titles don't match the expected field keywords")
    print("\n   Available sections:")
    for key in list(content_dict.keys())[:10]:
        print(f"   - {key}")
else:
    print(f"✅ Parser working! {populated}/{len(fields)} fields populated")
print("=" * 70)
