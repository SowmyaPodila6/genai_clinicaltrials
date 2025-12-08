# Clinical Trial Extraction Schemas

## Overview

All extraction schemas are now defined in `langgraph_custom/extraction_schemas.py` using **Pydantic v2**, ensuring type safety and validation across the extraction pipeline.

## Schema Structure

### Base Schema: ExtractionResult

Every field extraction returns:

```python
{
  "content": str,              # Extracted text preserving all formatting
  "page_references": List[int] # Pages where information appears
}
```

### Field-Specific Schemas (All inherit from ExtractionResult)

1. **StudyOverviewExtraction**
   - Study title, NCT ID, protocol number
   - Phase (I/II/III/IV)
   - Study type classification
   - Disease/condition, study duration

2. **BriefDescriptionExtraction**
   - 2-3 sentence summary of purpose
   - Rationale for study
   - Overall design overview

3. **PrimarySecondaryObjectivesExtraction**
   - PRIMARY objectives with definitions and timeframes
   - SECONDARY objectives with definitions and timeframes

4. **TreatmentArmsInterventionsExtraction**
   - All treatment arms with names
   - Interventions/drugs per arm
   - Dosing schedules and routes
   - Treatment duration
   - Comparator/combination therapy

5. **EligibilityCriteriaExtraction**
   - Inclusion criteria (enrollment requirements)
   - Exclusion criteria (disqualifying factors)

6. **EnrollmentParticipantFlowExtraction**
   - Target sample size
   - Actual enrollment numbers
   - Randomization methodology
   - Screening and allocation details

7. **AdverseEventsProfileExtraction**
   - Adverse events with frequencies/percentages
   - Serious adverse events (SAEs)
   - Toxicity grades
   - Safety profile data

8. **StudyLocationsExtraction**
   - Study sites and countries
   - Institutions
   - Principal investigators/coordinators

9. **SponsorInformationExtraction**
   - Primary sponsor
   - Collaborating institutions
   - Funding sources
   - Contact information

## Complete Result Schema: ClinicalTrialExtractionResult

Combines all 9 fields:

```python
{
  "study_overview": ExtractionResult,
  "brief_description": ExtractionResult,
  "primary_secondary_objectives": ExtractionResult,
  "treatment_arms_interventions": ExtractionResult,
  "eligibility_criteria": ExtractionResult,
  "enrollment_participant_flow": ExtractionResult,
  "adverse_events_profile": ExtractionResult,
  "study_locations": ExtractionResult,
  "sponsor_information": ExtractionResult
}
```

## Usage

### Getting Schemas

```python
from langgraph_custom.extraction_schemas import (
    get_extraction_result_schema_dict,      # Single field schema
    get_all_fields_schema_dict,             # Complete extraction schema
    FIELD_CONFIGS_WITH_SCHEMA,              # Field configs with metadata
    FIELD_SCHEMA_MAP,                       # Field name → schema class mapping
)

# Get schema for OpenAI API
schema = get_extraction_result_schema_dict()

# Get complete extraction schema
complete_schema = get_all_fields_schema_dict()
```

### Validating Results

```python
from langgraph_custom.extraction_schemas import ExtractionResult

# Validate extraction result
result = ExtractionResult(
    content="Extracted text...",
    page_references=[1, 2, 3]
)
```

## JSON Schema Structure

The schemas are automatically converted to JSON Schema format for OpenAI API:

```json
{
  "type": "object",
  "properties": {
    "content": {
      "type": "string",
      "description": "The extracted information as a single string..."
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
}
```

## Integration with LLM

The `MultiTurnExtractor` now uses structured outputs with these schemas:

```python
from langgraph_custom.multi_turn_extractor import MultiTurnExtractor

extractor = MultiTurnExtractor()
# All responses will conform to ExtractionResult schema
```

**OpenAI API Configuration:**
- Uses `json_schema` format
- Strict mode enabled (`strict: True`)
- Guarantees schema compliance
- Type validation enforced server-side

## Benefits

✅ **Type Safety** - Pydantic validates all fields  
✅ **Consistency** - All extractions follow same structure  
✅ **Documentation** - Self-documenting schema with descriptions  
✅ **Reusability** - Single source of truth for all schemas  
✅ **API Compliance** - OpenAI strict mode validation  
✅ **Easy Maintenance** - Centralized schema definitions  

## Field Metadata

Each field in `FIELD_CONFIGS_WITH_SCHEMA` includes:

- `schema_class` - Pydantic model for validation
- `keywords` - Search terms for text chunking
- `max_tokens` - Maximum tokens for this field
- `priority` - Processing priority (1=high, 3=low)
- `description` - Detailed field description
