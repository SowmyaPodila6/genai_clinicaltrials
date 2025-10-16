"""
Simple LangGraph Workflow for Clinical Trial Analysis
Following official LangGraph documentation patterns
Integrated with app_v1.py functionality
"""

from typing import TypedDict, Annotated, Literal, Iterator
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
import json
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

# Import existing parsers (using enhanced_parser as in app_v1)
from enhanced_parser import ClinicalTrialPDFParser
from clinical_trail_parser import map_sections_to_schema

load_dotenv()

# Initialize LLM with streaming support
llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

# System message for GPT-4 summarization (from app_v1)
SYSTEM_MESSAGE = "You are a clinical research summarization expert. Create concise, well-formatted summaries that focus only on available information. Avoid filler text and sections with insufficient data. Use clear markdown formatting and keep summaries under 400 words while including all key available information."

class WorkflowState(TypedDict):
    """State for the workflow following LangGraph patterns"""
    input_url: str
    input_type: Literal["pdf", "url", "unknown"]
    raw_data: dict  # Raw API response or PDF data
    parsed_json: dict  # Structured 9-field schema
    data_to_summarize: dict  # Formatted for GPT (like app_v1)
    confidence_score: float
    completeness_score: float
    missing_fields: list
    nct_id: str
    chat_query: str
    chat_response: str
    stream_response: Iterator  # For streaming
    error: str


def classify_input(state: WorkflowState) -> WorkflowState:
    """Node: Classify input as PDF or URL (same logic as app_v1)"""
    input_url = state["input_url"]
    
    if input_url.lower().endswith('.pdf') or 'pdf' in input_url.lower():
        state["input_type"] = "pdf"
    elif 'clinicaltrials.gov' in input_url.lower() or re.search(r"NCT\d{8}", input_url):
        state["input_type"] = "url"
    else:
        state["input_type"] = "unknown"
        state["error"] = "Invalid input type. Please provide a ClinicalTrials.gov URL or PDF file."
    
    return state


def route_input(state: WorkflowState) -> Literal["pdf_parser", "url_extractor", "error"]:
    """Conditional edge: Route based on input type"""
    if state["input_type"] == "pdf":
        return "pdf_parser"
    elif state["input_type"] == "url":
        return "url_extractor"
    else:
        return "error"


def parse_pdf(state: WorkflowState) -> WorkflowState:
    """Node: Parse PDF document using enhanced_parser (same as app_v1)"""
    try:
        parser = ClinicalTrialPDFParser()
        
        # Handle file path or URL
        if state["input_url"].startswith('http'):
            response = requests.get(state["input_url"])
            pdf_bytes = response.content
            sections = parser.parse_pdf_bytes(pdf_bytes)
        else:
            sections = parser.parse_pdf(state["input_url"])
        
        # Map to schema (9 fields)
        parsed_schema = map_sections_to_schema(sections)
        state["parsed_json"] = parsed_schema
        state["raw_data"] = {"sections": sections}  # Store raw sections
        
        # Convert to app_v1 format for summarization
        state["data_to_summarize"] = {
            "Study Overview": parsed_schema.get("study_overview", ""),
            "Brief Description": parsed_schema.get("brief_description", ""),
            "Primary and Secondary Objectives": parsed_schema.get("primary_secondary_objectives", ""),
            "Treatment Arms and Interventions": parsed_schema.get("treatment_arms_interventions", ""),
            "Eligibility Criteria": parsed_schema.get("eligibility_criteria", ""),
            "Enrollment and Participant Flow": parsed_schema.get("enrollment_participant_flow", ""),
            "Adverse Events Profile": parsed_schema.get("adverse_events_profile", ""),
            "Study Locations": parsed_schema.get("study_locations", ""),
            "Sponsor Information": parsed_schema.get("sponsor_information", "")
        }
        
        # Calculate metrics
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(parsed_schema)
        state["nct_id"] = "PDF-" + Path(state["input_url"]).stem
        
    except Exception as e:
        state["error"] = f"PDF parsing error: {str(e)}"
    
    return state


def extract_from_url(state: WorkflowState) -> WorkflowState:
    """Node: Extract data from ClinicalTrials.gov URL (EXACT copy of app_v1 get_protocol_data)"""
    try:
        # Extract NCT number
        nct_match = re.search(r"NCT\d{8}", state["input_url"])
        if not nct_match:
            state["error"] = "Invalid ClinicalTrials.gov URL - NCT number not found"
            return state
        
        nct_number = nct_match.group(0)
        state["nct_id"] = nct_number
        
        # Fetch from API (same as app_v1)
        api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_number}"
        response = requests.get(api_url)
        response.raise_for_status()
        
        study_data = response.json()
        state["raw_data"] = study_data
        
        protocol_section = study_data.get('protocolSection', {})
        results_section = study_data.get('resultsSection', {})
        
        if not protocol_section:
            state["error"] = "Error: Study data could not be found for this NCT number."
            return state

        # Extract all data EXACTLY as in app_v1.py
        # (This is a condensed version - the full extraction logic from app_v1)
        identification_module = protocol_section.get('identificationModule', {})
        official_title = identification_module.get('officialTitle', 'N/A')
        
        status_module = protocol_section.get('statusModule', {})
        overall_status = status_module.get('overallStatus', 'N/A')
        
        description_module = protocol_section.get('descriptionModule', {})
        brief_summary = description_module.get('briefSummary', 'N/A')
        
        design_module = protocol_section.get('designModule', {})
        study_type = design_module.get('studyType', 'N/A')
        study_phases = design_module.get('phases', [])
        study_phase = ", ".join(study_phases) if study_phases else 'N/A'
        
        arms_interventions_module = protocol_section.get('armsInterventionsModule', {})
        arm_groups_list = arms_interventions_module.get('armGroups', [])
        interventions_list = arms_interventions_module.get('interventions', [])
        
        # Format arms
        arm_groups_text = ""
        for i, ag in enumerate(arm_groups_list, 1):
            arm_label = ag.get('label', f'Arm {i}')
            arm_type = ag.get('type', 'N/A')
            arm_description = ag.get('description', 'N/A')
            intervention_names = ag.get('interventionNames', [])
            intervention_names_str = ", ".join(intervention_names) if intervention_names else "N/A"
            arm_groups_text += f"**Arm {i}: {arm_label}**\n  Type: {arm_type}\n  Description: {arm_description}\n  Interventions: {intervention_names_str}\n\n"
        
        # Format interventions
        interventions_text = ""
        for i, intervention in enumerate(interventions_list, 1):
            name = intervention.get('name', 'N/A')
            int_type = intervention.get('type', 'N/A')
            description = intervention.get('description', 'N/A')
            interventions_text += f"**Drug {i}: {name}**\n  Type: {int_type}\n  Description: {description}\n\n"
        
        eligibility_module = protocol_section.get('eligibilityModule', {})
        eligibility_criteria = eligibility_module.get('eligibilityCriteria', 'N/A')
        
        outcomes_module = protocol_section.get('outcomesModule', {})
        primary_outcomes = outcomes_module.get('primaryOutcomes', [])
        secondary_outcomes = outcomes_module.get('secondaryOutcomes', [])
        
        outcomes_text = "**Primary Objectives:**\n"
        for outcome in primary_outcomes[:5]:
            measure = outcome.get('measure', 'N/A')
            outcomes_text += f"- {measure}\n"
        
        if secondary_outcomes:
            outcomes_text += "\n**Secondary Objectives:**\n"
            for outcome in secondary_outcomes[:5]:
                measure = outcome.get('measure', 'N/A')
                outcomes_text += f"- {measure}\n"
        
        # Participant flow
        participant_flow_text = ""
        if results_section:
            participant_flow_module = results_section.get('participantFlowModule', {})
            groups = participant_flow_module.get('groups', [])
            if groups:
                participant_flow_text += "**Participant Enrollment:**\n"
                for group in groups:
                    group_title = group.get('title', 'N/A')
                    group_description = group.get('description', 'N/A')
                    participant_flow_text += f"- {group_title}: {group_description}\n"
        
        # Adverse events
        adverse_events_text = ""
        adverse_events_module = results_section.get('adverseEventsModule', {})
        serious_events = adverse_events_module.get('seriousEvents', [])
        other_events = adverse_events_module.get('otherEvents', [])
        
        if serious_events or other_events:
            adverse_events_text += "**Adverse Events Reported:**\n"
            if serious_events:
                adverse_events_text += f"- Serious events: {len(serious_events)}\n"
            if other_events:
                adverse_events_text += f"- Other events: {len(other_events)}\n"
        else:
            adverse_events_text = "No adverse events reported in the structured API data."
        
        # Locations
        contacts_locations_module = protocol_section.get('contactsLocationsModule', {})
        locations = contacts_locations_module.get('locations', [])
        location_text = ""
        if locations:
            location_text = f"{len(locations)} sites across multiple countries"
        
        # Sponsor
        sponsor_collaborators_module = protocol_section.get('sponsorCollaboratorsModule', {})
        lead_sponsor = sponsor_collaborators_module.get('leadSponsor', {})
        sponsor_name = lead_sponsor.get('name', 'N/A')
        sponsor_class = lead_sponsor.get('class', 'N/A')
        sponsor_info = f"Lead Sponsor: {sponsor_name} ({sponsor_class})"
        
        # Create data_to_summarize dict (same format as app_v1)
        data_to_summarize = {
            "Study Overview": f"{official_title} | Status: {overall_status} | Type: {study_type} - {study_phase}",
            "Brief Description": brief_summary,
            "Primary and Secondary Objectives": outcomes_text if outcomes_text else None,
            "Treatment Arms and Interventions": f"{arm_groups_text}\n\n{interventions_text}" if (arm_groups_text or interventions_text) else None,
            "Eligibility Criteria": eligibility_criteria,
            "Enrollment and Participant Flow": participant_flow_text if participant_flow_text else None,
            "Adverse Events Profile": adverse_events_text if adverse_events_text and "No adverse events reported" not in adverse_events_text else None,
            "Study Locations": location_text if location_text else None,
            "Sponsor Information": sponsor_info if sponsor_info and sponsor_name != "N/A" else None
        }
        
        state["data_to_summarize"] = data_to_summarize
        state["parsed_json"] = data_to_summarize  # For consistency
        
        # Calculate metrics
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(data_to_summarize)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            state["error"] = f"Error: Study with NCT number was not found on ClinicalTrials.gov."
        else:
            state["error"] = f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        state["error"] = f"An error occurred while fetching the protocol: {e}"
    
    return state


def calculate_metrics(parsed_json: dict) -> tuple[float, float, list]:
    """Calculate confidence and completeness scores"""
    required_fields = [
        "study_overview",
        "brief_description",
        "primary_secondary_objectives",
        "treatment_arms_interventions",
        "eligibility_criteria",
        "enrollment_participant_flow",
        "adverse_events_profile",
        "study_locations",
        "sponsor_information"
    ]
    
    filled_fields = 0
    missing_fields = []
    total_content = 0
    
    for field in required_fields:
        content = parsed_json.get(field, "")
        if content and len(content.strip()) > 20:
            filled_fields += 1
            total_content += len(content)
        else:
            missing_fields.append(field)
    
    completeness_score = filled_fields / len(required_fields)
    
    # Confidence based on content richness
    avg_content_length = total_content / max(filled_fields, 1)
    confidence_score = min(1.0, avg_content_length / 500)
    
    return confidence_score, completeness_score, missing_fields


def check_quality(state: WorkflowState) -> Literal["llm_fallback", "chat_node"]:
    """Conditional edge: Check if LLM fallback is needed"""
    if state["confidence_score"] < 0.5 or state["completeness_score"] < 0.6:
        return "llm_fallback"
    else:
        return "chat_node"


def llm_fallback(state: WorkflowState) -> WorkflowState:
    """Node: Use LLM to extract missing fields from full document"""
    try:
        # Get full document text
        if state["input_type"] == "pdf":
            parser = ClinicalTrialPDFParser()
            if state["input_url"].startswith('http'):
                response = requests.get(state["input_url"])
                full_text = parser.extract_text_from_bytes(response.content)
            else:
                full_text = parser.extract_text(state["input_url"])
        else:
            full_text = json.dumps(state["raw_data"], indent=2)
        
        # LLM extraction prompt
        system_prompt = """You are a clinical trial data extraction expert. 
Extract the following fields from the document. 
Preserve original content exactly with references, do not modify or summarize.

Required fields:
1. study_overview
2. brief_description
3. primary_secondary_objectives
4. treatment_arms_interventions
5. eligibility_criteria
6. enrollment_participant_flow
7. adverse_events_profile
8. study_locations
9. sponsor_information

Return as JSON."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Document:\n\n{full_text[:15000]}")  # Limit token size
        ]
        
        response = llm.invoke(messages)
        
        # Parse LLM response
        try:
            llm_extracted = json.loads(response.content)
            # Merge with existing data
            state["parsed_json"].update(llm_extracted)
        except json.JSONDecodeError:
            # Fallback: use as-is
            state["parsed_json"]["llm_extracted_content"] = response.content
        
        # Recalculate metrics
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(state["parsed_json"])
        
    except Exception as e:
        state["error"] = f"LLM fallback error: {str(e)}"
    
    return state


def chat_node(state: WorkflowState) -> WorkflowState:
    """Node: Handle chat interactions with Q&A (with streaming support like app_v1)"""
    try:
        query = state.get("chat_query", "")
        
        if not query or query == "generate_summary":
            # Generate initial summary using EXACT app_v1 prompt
            data_to_summarize = state["data_to_summarize"]
            
            # Filter sections with meaningful content (same as app_v1)
            sections_to_include = {}
            for section, content in data_to_summarize.items():
                if (content and 
                    content != "N/A" and 
                    isinstance(content, str) and
                    "No " not in content[:20] and
                    "not available" not in content.lower() and
                    len(content.strip()) > 30):
                    sections_to_include[section] = content
            
            # Prepare consolidated content
            consolidated_content = ""
            for section, content in sections_to_include.items():
                consolidated_content += f"\n\n**{section}:**\n{content}\n"
            
            # EXACT prompt from app_v1
            study_title = data_to_summarize.get('Study Overview', '').split('|')[0].strip() if data_to_summarize.get('Study Overview') else 'Clinical Trial Protocol'
            
            concise_prompt = f"""Generate a concise, well-formatted clinical trial summary using ONLY the information provided below. Follow this structure and format:

# Clinical Trial Summary
## {study_title}

### Study Overview
- Disease: [Extract disease information]
- Phase: [Extract phase information]
- Design: [Extract design information]
- Brief Description: [Extract brief description - 2-3 sentences max]


### Primary Objectives
[List main safety and/or efficacy endpoints - bullet points, be specific]

### Treatment Arms & Interventions
[Create a simple table if multiple arms exist, otherwise describe briefly]

### Eligibility Criteria
#### Key inclusion criteria
#### Key exclusion criteria

### Enrollment & Participant Flow
[Patient numbers and enrollment status if available]

### Safety Profile
[Only include if adverse events data is available - summarize key findings]

---

**Available Data:**
{consolidated_content}

**Formatting Requirements:**
- Start with just "Clinical Trial Summary" as the main heading (NCT ID will be in header)
- Use the study title as the secondary heading
- Use clear section headers (###)
- Keep each section to 1-3 sentences or a simple table
- Do not skip any key details if available; do not fabricate missing info; strictly summarize the content from the Protocol.
- Use bullet points for lists
- Only include sections where meaningful data exists
- Skip any section that says "not available" or has insufficient information
- Make it readable and concise - aim for 200-400 words total
- Use markdown formatting for better readability"""

            messages = [
                SystemMessage(content="You are a clinical research summarization expert. Create concise, well-formatted summaries that focus only on available information. Avoid filler text and sections with insufficient data. Use clear markdown formatting and keep summaries under 400 words while including all key available information."),
                HumanMessage(content=concise_prompt)
            ]
        else:
            # Follow-up question handling (same as app_v1)
            context = json.dumps(state["data_to_summarize"], indent=2)
            
            system_prompt = "You are a medical summarization assistant. Answer questions based on the provided protocol text. Do not invent information."
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Clinical Trial Data:\n{context}\n\nQuestion: {query}")
            ]
        
        # Stream response
        response_text = ""
        for chunk in llm.stream(messages):
            if hasattr(chunk, 'content'):
                response_text += chunk.content
        
        state["chat_response"] = response_text
        
    except Exception as e:
        state["error"] = f"Chat error: {str(e)}"
        state["chat_response"] = "Error processing query"
    
    return state


def chat_node_stream(state: WorkflowState) -> Iterator[str]:
    """Node: Handle chat with streaming (for Streamlit display)"""
    try:
        query = state.get("chat_query", "")
        
        if not query or query == "generate_summary":
            # Generate initial summary
            data_to_summarize = state["data_to_summarize"]
            
            # Filter sections
            sections_to_include = {}
            for section, content in data_to_summarize.items():
                if (content and 
                    content != "N/A" and 
                    isinstance(content, str) and
                    "No " not in content[:20] and
                    "not available" not in content.lower() and
                    len(content.strip()) > 30):
                    sections_to_include[section] = content
            
            consolidated_content = ""
            for section, content in sections_to_include.items():
                consolidated_content += f"\n\n**{section}:**\n{content}\n"
            
            study_title = data_to_summarize.get('Study Overview', '').split('|')[0].strip() if data_to_summarize.get('Study Overview') else 'Clinical Trial Protocol'
            
            concise_prompt = f"""Generate a concise, well-formatted clinical trial summary using ONLY the information provided below. Follow this structure and format:

# Clinical Trial Summary
## {study_title}

### Study Overview
- Disease: [Extract disease information]
- Phase: [Extract phase information]
- Design: [Extract design information]
- Brief Description: [Extract brief description - 2-3 sentences max]


### Primary Objectives
[List main safety and/or efficacy endpoints - bullet points, be specific]

### Treatment Arms & Interventions
[Create a simple table if multiple arms exist, otherwise describe briefly]

### Eligibility Criteria
#### Key inclusion criteria
#### Key exclusion criteria

### Enrollment & Participant Flow
[Patient numbers and enrollment status if available]

### Safety Profile
[Only include if adverse events data is available - summarize key findings]

---

**Available Data:**
{consolidated_content}

**Formatting Requirements:**
- Start with just "Clinical Trial Summary" as the main heading (NCT ID will be in header)
- Use the study title as the secondary heading
- Use clear section headers (###)
- Keep each section to 1-3 sentences or a simple table
- Do not skip any key details if available; do not fabricate missing info; strictly summarize the content from the Protocol.
- Use bullet points for lists
- Only include sections where meaningful data exists
- Skip any section that says "not available" or has insufficient information
- Make it readable and concise - aim for 200-400 words total
- Use markdown formatting for better readability"""

            messages = [
                SystemMessage(content="You are a clinical research summarization expert. Create concise, well-formatted summaries that focus only on available information. Avoid filler text and sections with insufficient data. Use clear markdown formatting and keep summaries under 400 words while including all key available information."),
                HumanMessage(content=concise_prompt)
            ]
        else:
            context = json.dumps(state["data_to_summarize"], indent=2)
            system_prompt = "You are a medical summarization assistant. Answer questions based on the provided protocol text. Do not invent information."
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Clinical Trial Data:\n{context}\n\nQuestion: {query}")
            ]
        
        # Stream chunks
        for chunk in llm.stream(messages):
            if hasattr(chunk, 'content'):
                yield chunk.content
                
    except Exception as e:
        yield f"Error: {str(e)}"


def convert_api_to_schema(study_data: dict) -> dict:
    """Convert ClinicalTrials.gov API data to standard schema (deprecated - using extract_from_url instead)"""
    # This function is kept for backward compatibility but not used in main workflow
    protocol = study_data.get('protocolSection', {})
    
    identification = protocol.get('identificationModule', {})
    description = protocol.get('descriptionModule', {})
    design = protocol.get('designModule', {})
    arms = protocol.get('armsInterventionsModule', {})
    eligibility = protocol.get('eligibilityModule', {})
    contacts = protocol.get('contactsLocationsModule', {})
    sponsor = protocol.get('sponsorCollaboratorsModule', {})
    outcomes = protocol.get('outcomesModule', {})
    
    return {
        "study_overview": identification.get('officialTitle', ''),
        "brief_description": description.get('briefSummary', ''),
        "primary_secondary_objectives": json.dumps({
            'primary': outcomes.get('primaryOutcomes', []),
            'secondary': outcomes.get('secondaryOutcomes', [])
        }),
        "treatment_arms_interventions": json.dumps({
            'arms': arms.get('armGroups', []),
            'interventions': arms.get('interventions', [])
        }),
        "eligibility_criteria": eligibility.get('eligibilityCriteria', ''),
        "enrollment_participant_flow": json.dumps(design.get('enrollmentInfo', {})),
        "adverse_events_profile": "Not available in protocol section",
        "study_locations": json.dumps(contacts.get('locations', [])),
        "sponsor_information": json.dumps(sponsor)
    }


# Build the graph
def build_workflow() -> StateGraph:
    """Build the LangGraph workflow"""
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("classify_input", classify_input)
    workflow.add_node("pdf_parser", parse_pdf)
    workflow.add_node("url_extractor", extract_from_url)
    workflow.add_node("llm_fallback", llm_fallback)
    workflow.add_node("chat_node", chat_node)
    
    # Add edges
    workflow.set_entry_point("classify_input")
    
    workflow.add_conditional_edges(
        "classify_input",
        route_input,
        {
            "pdf_parser": "pdf_parser",
            "url_extractor": "url_extractor",
            "error": END
        }
    )
    
    workflow.add_conditional_edges(
        "pdf_parser",
        check_quality,
        {
            "llm_fallback": "llm_fallback",
            "chat_node": "chat_node"
        }
    )
    
    workflow.add_conditional_edges(
        "url_extractor",
        check_quality,
        {
            "llm_fallback": "llm_fallback",
            "chat_node": "chat_node"
        }
    )
    
    workflow.add_edge("llm_fallback", "chat_node")
    workflow.add_edge("chat_node", END)
    
    return workflow.compile()


# Main execution
if __name__ == "__main__":
    app = build_workflow()
    
    # Example usage
    result = app.invoke({
        "input_url": "https://clinicaltrials.gov/study/NCT03991871",
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
        "stream_response": None,
        "error": ""
    })
    
    print(json.dumps(result, indent=2, default=str))
