"""Simple test to see actual output"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from enhanced_parser import parse_clinical_trial_pdf
import json

print("Testing HIV-HIV-2018-Molloy PDF...")
result = parse_clinical_trial_pdf("HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf")

print(f"\nConfidence: {result['confidence_score']:.1%}")
print(f"Pages: {result['total_pages']}")

fields = [
    'study_overview', 'brief_description', 'primary_secondary_objectives',
    'treatment_arms_interventions', 'eligibility_criteria',
    'enrollment_participant_flow', 'adverse_events_profile',
    'study_locations', 'sponsor_information'
]

print("\nFields:")
for field in fields:
    val = result[field]
    print(f"  {field}: {len(val)} chars - {'YES' if val.strip() else 'NO'}")

# Save to file for inspection
with open("test_output_simple.json", "w", encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
    
print("\nSaved to test_output_simple.json")
