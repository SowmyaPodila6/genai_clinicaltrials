# Clinical Trial Extraction Example Output

## Complete Extraction Result

This shows what a complete extraction result looks like using the Pydantic schemas:

```json
{
  "study_overview": {
    "content": "Study Title: A Phase II Randomized Controlled Trial of Novel Treatment X in Advanced Cancer Patients\nNCT ID: NCT04123456\nProtocol Number: PROTO-2024-001\nPhase: II\nStudy Type: Randomized, Controlled, Double-Blinded\nDisease: Advanced Non-Small Cell Lung Cancer\nStudy Duration: 24 months",
    "page_references": [1, 2]
  },
  "brief_description": {
    "content": "This study evaluates the efficacy and safety of novel treatment X compared to standard of care in patients with advanced non-small cell lung cancer. The study hypothesizes that X will improve progression-free survival by 40% compared to control.",
    "page_references": [2]
  },
  "primary_secondary_objectives": {
    "content": "PRIMARY OBJECTIVE:\n- To evaluate the efficacy of treatment X versus control in improving progression-free survival (PFS) at 12 months\n\nSECONDARY OBJECTIVES:\n- To evaluate overall survival (OS) at 24 months\n- To assess overall response rate (ORR)\n- To evaluate safety profile and tolerability\n- To assess quality of life using EORTC QLQ-C30",
    "page_references": [3, 4]
  },
  "treatment_arms_interventions": {
    "content": "ARM 1 (Treatment): Novel Treatment X\n- Drug: X compound\n- Dose: 250 mg daily\n- Route: Oral\n- Schedule: Once daily with food\n- Duration: Continuous until progression or toxicity\n\nARM 2 (Control): Standard of Care\n- Drug: Conventional chemotherapy\n- Dose: Standard approved dosing\n- Route: Intravenous\n- Schedule: Every 21 days for up to 6 cycles\n- Duration: 6 cycles or until progression",
    "page_references": [5, 6]
  },
  "eligibility_criteria": {
    "content": "INCLUSION CRITERIA:\n- Age 18-75 years\n- Histologically confirmed advanced NSCLC\n- ECOG performance status 0-1\n- Measurable disease per RECIST 1.1\n- Adequate organ function (creatinine < 2.0 mg/dL, AST/ALT < 3x ULN)\n- Written informed consent\n\nEXCLUSION CRITERIA:\n- Prior treatment with X compound\n- Active secondary malignancy\n- Uncontrolled brain metastases\n- Pregnancy or nursing\n- Active infection requiring systemic therapy\n- Significant cardiac disease",
    "page_references": [7, 8]
  },
  "enrollment_participant_flow": {
    "content": "TARGET SAMPLE SIZE: 200 participants (100 per arm)\n\nACTUAL ENROLLMENT: 205 participants\n\nRANDOMIZATION:\n- Method: 1:1 block randomization\n- Stratification factors: ECOG score, prior therapy\n\nPARTICIPANT FLOW:\nScreening (n=412) → Enrollment (n=205) → \n  ARM 1 (n=102) → Completed treatment: 89 → Discontinued: 13\n  ARM 2 (n=103) → Completed treatment: 95 → Discontinued: 8\n\nREASONS FOR DISCONTINUATION:\n- Adverse events: 12\n- Disease progression: 7\n- Withdrew consent: 2",
    "page_references": [9, 10]
  },
  "adverse_events_profile": {
    "content": "COMMON ADVERSE EVENTS (Grade ≥2):\nTreatment Arm:\n- Nausea: 45% (Grade 3: 8%)\n- Fatigue: 52% (Grade 3: 12%)\n- Diarrhea: 38% (Grade 3: 6%)\n- Rash: 28% (Grade 3: 4%)\n\nControl Arm:\n- Nausea: 40% (Grade 3: 12%)\n- Fatigue: 48% (Grade 3: 15%)\n- Alopecia: 90% (Grade 3: 45%)\n\nSERIOUS ADVERSE EVENTS:\n- Treatment arm: 8 cases (7.8%)\n- Control arm: 12 cases (11.7%)\n- Most common: Neutropenia, febrile illness",
    "page_references": [11, 12, 13]
  },
  "study_locations": {
    "content": "STUDY SITES: 12 institutions across 5 countries\n\nUnited States:\n- Memorial Sloan Kettering Cancer Center, New York - PI: Dr. John Smith\n- MD Anderson Cancer Center, Houston - PI: Dr. Sarah Johnson\n- Stanford University, Palo Alto - PI: Dr. Michael Chen\n\nCanada:\n- Princess Margaret Hospital, Toronto - PI: Dr. Lisa Wong\n- BC Cancer Agency, Vancouver - PI: Dr. Robert Brown\n\nEurope:\n- Institut Gustave Roussy, Paris - PI: Dr. François Dupont\n- Royal Marsden Hospital, London - PI: Dr. Elizabeth Taylor\n\n[Additional sites listed with PI information]",
    "page_references": [14, 15]
  },
  "sponsor_information": {
    "content": "PRIMARY SPONSOR: BioPharma Therapeutics Inc.\nAddress: 100 Innovation Drive, San Francisco, CA 94102\nContact: Dr. Amanda Martinez (amanda.martinez@biopharm.com)\n\nCOLLABORATING INSTITUTIONS:\n- National Cancer Institute (US)\n- European Organization for Research and Treatment of Cancer (EORTC)\n- Cancer Research UK\n\nFUNDING SOURCES:\n- BioPharma Therapeutics Inc. (primary funding)\n- National Institute of Health Grant CA-2024-001\n- Patient advocacy foundation grant $500,000\n\nCLINICAL TRIAL REGISTRATION:\n- ClinicalTrials.gov: NCT04123456\n- EudraCT: 2024-001234-45",
    "page_references": [1, 16]
  }
}
```

## Individual Field Example

Each field follows the `ExtractionResult` schema:

```python
{
  "content": "[Verbatim text from document preserving all original formatting]",
  "page_references": [1, 2, 5, 7]
}
```

## Schema Validation

All results are validated against Pydantic models:

```python
from langgraph_custom.extraction_schemas import ExtractionResult

# Valid result
result = ExtractionResult(
    content="Study Title: NCT04123456...",
    page_references=[1, 2, 3]
)

# Invalid - will raise validation error
# result = ExtractionResult(
#     content={"data": "value"},  # Must be string!
#     page_references=[1, 2]
# )
```

## OpenAI Structured Output Format

The JSON schema sent to OpenAI API:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "clinical_trial_extraction",
    "description": "Structured extraction of clinical trial information with content and page references",
    "schema": {
      "type": "object",
      "properties": {
        "content": {
          "type": "string",
          "description": "The extracted information as a single string, preserving all original formatting, bullet points, and details"
        },
        "page_references": {
          "type": "array",
          "items": {
            "type": "integer"
          },
          "description": "List of page numbers where this information appears"
        }
      },
      "required": ["content", "page_references"],
      "additionalProperties": false
    },
    "strict": true
  }
}
```

## Data Types

| Field | Type | Example |
|-------|------|---------|
| `content` | `str` | "Phase II Randomized..." |
| `page_references` | `List[int]` | [1, 2, 5] |

All fields are required. No additional properties allowed (strict mode).
