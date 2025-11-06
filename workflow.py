"""
LangGraph Workflow for Clinical Trial Analysis
Clean, production-ready implementation following official LangGraph patterns
"""

from typing import TypedDict, Literal, Iterator
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

# Import local modules
from clinical_trail_parser import ClinicalTrialPDFParser, map_sections_to_schema
from prompts import (
    SUMMARIZATION_SYSTEM_PROMPT, 
    SUMMARY_GENERATION_TEMPLATE,
    QA_SYSTEM_PROMPT,
    QA_TEMPLATE
)
from utils import calculate_metrics, filter_meaningful_sections, create_consolidated_content

load_dotenv()

# Initialize LLM with streaming support
llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)


class WorkflowState(TypedDict):
    """State for the workflow"""
    input_url: str
    input_type: Literal["pdf", "url", "unknown"]
    raw_data: dict
    parsed_json: dict
    data_to_summarize: dict
    confidence_score: float
    completeness_score: float
    missing_fields: list
    nct_id: str
    chat_query: str
    chat_response: str
    error: str


def classify_input(state: WorkflowState) -> WorkflowState:
    """Node: Classify input as PDF or URL"""
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
    """Node: Parse PDF document"""
    try:
        parser = ClinicalTrialPDFParser()
        
        # Handle file path or URL
        if state["input_url"].startswith('http'):
            response = requests.get(state["input_url"])
            pdf_bytes = response.content
            sections = parser.parse_pdf_bytes(pdf_bytes)
        else:
            sections = parser.parse_pdf_file(state["input_url"])
        
        # Map to schema (9 fields)
        parsed_schema = map_sections_to_schema(sections)
        state["parsed_json"] = parsed_schema
        state["raw_data"] = {"sections": sections}
        
        # Convert to summarization format
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
    """Node: Extract data from ClinicalTrials.gov URL"""
    try:
        # Extract NCT number
        nct_match = re.search(r"NCT\d{8}", state["input_url"])
        if not nct_match:
            state["error"] = "Invalid ClinicalTrials.gov URL - NCT number not found"
            return state
        
        nct_number = nct_match.group(0)
        state["nct_id"] = nct_number
        
        # Fetch from API
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

        # Extract key sections
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
        
        # Create data_to_summarize dict
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
        state["parsed_json"] = data_to_summarize
        
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
                sections = parser.parse_pdf_bytes(response.content)
            else:
                sections = parser.parse_pdf_file(state["input_url"])
            full_text = json.dumps(sections, indent=2)
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
            state["data_to_summarize"].update(llm_extracted)
        except json.JSONDecodeError:
            # Fallback: use as-is
            pass
        
        # Recalculate metrics
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(state["data_to_summarize"])
        
    except Exception as e:
        state["error"] = f"LLM fallback error: {str(e)}"
    
    return state


def chat_node(state: WorkflowState) -> WorkflowState:
    """Node: Handle chat interactions with Q&A"""
    try:
        query = state.get("chat_query", "")
        
        if not query or query == "generate_summary":
            # Generate initial summary
            data_to_summarize = state["data_to_summarize"]
            sections_to_include = filter_meaningful_sections(data_to_summarize)
            consolidated_content = create_consolidated_content(sections_to_include)
            
            study_title = data_to_summarize.get('Study Overview', '').split('|')[0].strip() if data_to_summarize.get('Study Overview') else 'Clinical Trial Protocol'
            
            concise_prompt = SUMMARY_GENERATION_TEMPLATE.format(
                study_title=study_title,
                consolidated_content=consolidated_content
            )

            messages = [
                SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT),
                HumanMessage(content=concise_prompt)
            ]
        else:
            # Follow-up question handling
            context = json.dumps(state["data_to_summarize"], indent=2)
            
            question_prompt = QA_TEMPLATE.format(
                context=context,
                query=query
            )
            
            messages = [
                SystemMessage(content=QA_SYSTEM_PROMPT),
                HumanMessage(content=question_prompt)
            ]
        
        # Get response
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
            sections_to_include = filter_meaningful_sections(data_to_summarize)
            consolidated_content = create_consolidated_content(sections_to_include)
            
            study_title = data_to_summarize.get('Study Overview', '').split('|')[0].strip() if data_to_summarize.get('Study Overview') else 'Clinical Trial Protocol'
            
            concise_prompt = SUMMARY_GENERATION_TEMPLATE.format(
                study_title=study_title,
                consolidated_content=consolidated_content
            )

            messages = [
                SystemMessage(content=SUMMARIZATION_SYSTEM_PROMPT),
                HumanMessage(content=concise_prompt)
            ]
        else:
            # Follow-up question
            context = json.dumps(state["data_to_summarize"], indent=2)
            question_prompt = QA_TEMPLATE.format(context=context, query=query)
            messages = [
                SystemMessage(content=QA_SYSTEM_PROMPT),
                HumanMessage(content=question_prompt)
            ]
        
        # Stream chunks
        for chunk in llm.stream(messages):
            if hasattr(chunk, 'content'):
                yield chunk.content
                
    except Exception as e:
        yield f"Error: {str(e)}"


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
        "error": ""
    })
    
    print(json.dumps(result, indent=2, default=str))
