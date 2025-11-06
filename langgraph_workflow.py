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

# Import parsers - use EnhancedClinicalTrialParser for better accuracy
from enhanced_parser import EnhancedClinicalTrialParser, ClinicalTrialData
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
    used_llm_fallback: bool  # Track if LLM fallback was used


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
    """Node: Parse PDF document using EnhancedClinicalTrialParser for better accuracy"""
    try:
        # Use enhanced parser with advanced features
        parser = EnhancedClinicalTrialParser(use_ocr=False, use_nlp=False)
        
        file_path = state["input_url"]
        
        # Handle file path or URL
        if file_path.startswith('http'):
            # Download PDF temporarily
            response = requests.get(file_path)
            temp_path = f"temp_download_{Path(file_path).stem}.pdf"
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            file_path = temp_path
        
        # Parse PDF with enhanced parser
        clinical_data, tables = parser.parse_pdf(file_path, extract_tables=True)
        
        # Convert ClinicalTrialData to dict
        from dataclasses import asdict
        parsed_schema = {
            "study_overview": clinical_data.study_overview,
            "brief_description": clinical_data.brief_description,
            "primary_secondary_objectives": clinical_data.primary_secondary_objectives,
            "treatment_arms_interventions": clinical_data.treatment_arms_interventions,
            "eligibility_criteria": clinical_data.eligibility_criteria,
            "enrollment_participant_flow": clinical_data.enrollment_participant_flow,
            "adverse_events_profile": clinical_data.adverse_events_profile,
            "study_locations": clinical_data.study_locations,
            "sponsor_information": clinical_data.sponsor_information
        }
        
        state["parsed_json"] = parsed_schema
        state["raw_data"] = {"clinical_data": asdict(clinical_data), "tables": [asdict(t) for t in tables]}
        
        # Convert to display format for summarization
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
        
        # Clean up temp file if downloaded
        if state["input_url"].startswith('http'):
            import os
            if os.path.exists(file_path):
                os.remove(file_path)
        
    except Exception as e:
        state["error"] = f"PDF parsing error: {str(e)}"
    
    return state


def extract_from_url(state: WorkflowState) -> WorkflowState:
    """Node: Extract data from ClinicalTrials.gov URL - EXACT copy of original get_protocol_data"""
    try:
        # Extract NCT number
        nct_match = re.search(r"NCT\d{8}", state["input_url"])
        if not nct_match:
            state["error"] = "Invalid ClinicalTrials.gov URL - NCT number not found"
            return state
        
        nct_number = nct_match.group(0)
        
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

        # Identification Module
        identification_module = protocol_section.get('identificationModule', {})
        nct_id = identification_module.get('nctId', 'N/A')
        official_title = identification_module.get('officialTitle', 'N/A')
        state["nct_id"] = nct_id

        # Status Module
        status_module = protocol_section.get('statusModule', {})
        overall_status = status_module.get('overallStatus', 'N/A')
        
        # Description Module
        description_module = protocol_section.get('descriptionModule', {})
        brief_summary = description_module.get('briefSummary', 'N/A')
        detailed_description = description_module.get('detailedDescription', 'N/A')
        
        # Design Module
        design_module = protocol_section.get('designModule', {})
        study_type = design_module.get('studyType', 'N/A')
        study_phases = design_module.get('phases', [])
        study_phase = ", ".join(study_phases) if study_phases else 'N/A'
        
        design_info = design_module.get('designInfo', {})
        allocation = design_info.get('allocation', 'N/A')
        intervention_model = design_info.get('interventionModel', 'N/A')
        primary_purpose = design_info.get('primaryPurpose', 'N/A')
        
        masking_info = design_info.get('maskingInfo', {})
        masking = masking_info.get('masking', 'N/A')
        who_masked = masking_info.get('whoMasked', [])
        who_masked_str = ", ".join(who_masked) if who_masked else 'N/A'
        
        enrollment_info = design_module.get('enrollmentInfo', {})
        enrollment_count = enrollment_info.get('count', 'N/A')
        enrollment_type = enrollment_info.get('type', 'N/A')
        
        study_design_text = f"Study Type: {study_type}\nPhases: {study_phase}\nAllocation: {allocation}\nIntervention Model: {intervention_model}\nPrimary Purpose: {primary_purpose}\nMasking: {masking}\nWho Masked: {who_masked_str}\nEnrollment: {enrollment_count} ({enrollment_type})"
        
        # Interventions and Arm Groups
        arms_interventions_module = protocol_section.get('armsInterventionsModule', {})
        arm_groups_list = arms_interventions_module.get('armGroups', [])
        if not isinstance(arm_groups_list, list):
            arm_groups_list = []
        
        # Extract arm groups with enhanced dosing information
        arm_groups_text = ""
        for i, ag in enumerate(arm_groups_list, 1):
            arm_label = ag.get('label', f'Arm {i}')
            arm_type = ag.get('type', 'N/A')
            arm_description = ag.get('description', 'N/A')
            intervention_names = ag.get('interventionNames', [])
            intervention_names_str = ", ".join(intervention_names) if intervention_names else "N/A"
            
            # Try to extract dose information from description
            dose_info = ""
            if arm_description and arm_description != 'N/A':
                # Look for common dose patterns
                dose_patterns = [
                    r'(\d+(?:\.\d+)?)\s*mg/kg',  # mg/kg dosing
                    r'(\d+(?:\.\d+)?)\s*mg/m2',  # mg/m2 dosing  
                    r'(\d+(?:\.\d+)?)\s*mg',     # mg dosing
                    r'(\d+(?:\.\d+)?)\s*mcg',    # mcg dosing
                    r'(\d+(?:\.\d+)?)\s*units',  # units
                ]
                
                found_doses = []
                for pattern in dose_patterns:
                    matches = re.findall(pattern, arm_description, re.IGNORECASE)
                    if matches:
                        unit = pattern.split('\\s*')[1].replace(')', '')
                        for match in matches:
                            found_doses.append(f"{match} {unit}")
                
                if found_doses:
                    dose_info = f"  Doses: {', '.join(found_doses)}\n"
            
            arm_groups_text += f"**Arm {i}: {arm_label}**\n  Type: {arm_type}\n  Description: {arm_description}\n{dose_info}  Interventions: {intervention_names_str}\n\n"
        
        # Extract interventions with correct field names
        interventions_list = arms_interventions_module.get('interventions', [])
        if not isinstance(interventions_list, list):
            interventions_list = []
        
        # Extract interventions with enhanced drug information
        interventions_text = ""
        for i, intervention in enumerate(interventions_list, 1):
            name = intervention.get('name', 'N/A')
            int_type = intervention.get('type', 'N/A')
            description = intervention.get('description', 'N/A')
            arm_group_labels = intervention.get('armGroupLabels', [])
            other_names = intervention.get('otherNames', [])
            
            arm_labels_str = ", ".join(arm_group_labels) if arm_group_labels else "N/A"
            other_names_str = ", ".join(other_names) if other_names else "N/A"
            
            # Extract drug class or mechanism information from other names
            drug_info = ""
            if other_names:
                for other_name in other_names:
                    if any(keyword in other_name.upper() for keyword in ['ANTI-', 'INHIBITOR', 'AGONIST', 'ANTAGONIST']):
                        drug_info = f"  Mechanism: {other_name}\n"
                        break
            
            interventions_text += f"**Drug {i}: {name}**\n  Type: {int_type}\n  Description: {description}\n{drug_info}  Used in Arms: {arm_labels_str}\n  Other Names/Codes: {other_names_str}\n\n"

        # Eligibility Module
        eligibility_module = protocol_section.get('eligibilityModule', {})
        eligibility_criteria_data = eligibility_module.get('eligibilityCriteria', 'N/A')
        if isinstance(eligibility_criteria_data, dict):
            eligibility_criteria = eligibility_criteria_data.get('textblock', 'N/A')
        else:
            eligibility_criteria = eligibility_criteria_data
        
        # Enhanced outcomes extraction with objective identification
        outcomes_module = protocol_section.get('outcomesModule', {})
        primary_outcomes = outcomes_module.get('primaryOutcomes', [])
        secondary_outcomes = outcomes_module.get('secondaryOutcomes', [])
        
        outcomes_text = ""
        
        # Extract and categorize primary outcomes
        if primary_outcomes:
            safety_outcomes = []
            efficacy_outcomes = []
            pk_outcomes = []
            
            for outcome in primary_outcomes:
                measure = outcome.get('measure', 'N/A')
                description = outcome.get('description', 'N/A')
                time_frame = outcome.get('timeFrame', 'N/A')
                
                # Categorize outcomes based on keywords
                measure_lower = measure.lower()
                if any(keyword in measure_lower for keyword in ['safety', 'adverse', 'toxicity', 'mtd', 'dose']):
                    safety_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                elif any(keyword in measure_lower for keyword in ['response', 'efficacy', 'survival', 'progression']):
                    efficacy_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                elif any(keyword in measure_lower for keyword in ['pharmacokinetic', 'concentration', 'clearance']):
                    pk_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
                else:
                    efficacy_outcomes.append({'measure': measure, 'description': description, 'time_frame': time_frame})
            
            outcomes_text += "**Primary Objectives:**\n"
            
            if safety_outcomes:
                outcomes_text += "\n*Safety Objectives:*\n"
                for outcome in safety_outcomes:
                    outcomes_text += f"- {outcome['measure']}\n  Description: {outcome['description']}\n  Time Frame: {outcome['time_frame']}\n\n"
            
            if efficacy_outcomes:
                outcomes_text += "\n*Efficacy Objectives:*\n"
                for outcome in efficacy_outcomes:
                    outcomes_text += f"- {outcome['measure']}\n  Description: {outcome['description']}\n  Time Frame: {outcome['time_frame']}\n\n"
            
            if pk_outcomes:
                outcomes_text += "\n*Pharmacokinetic Objectives:*\n"
                for outcome in pk_outcomes:
                    outcomes_text += f"- {outcome['measure']}\n  Description: {outcome['description']}\n  Time Frame: {outcome['time_frame']}\n\n"
        
        # Extract secondary outcomes
        if secondary_outcomes:
            outcomes_text += "**Secondary Objectives:**\n"
            for i, outcome in enumerate(secondary_outcomes[:10], 1):  # Limit to first 10
                measure = outcome.get('measure', 'N/A')
                description = outcome.get('description', 'N/A')
                time_frame = outcome.get('timeFrame', 'N/A')
                outcomes_text += f"{i}. {measure}\n   Description: {description}\n   Time Frame: {time_frame}\n\n"
            
            if len(secondary_outcomes) > 10:
                outcomes_text += f"... and {len(secondary_outcomes)-10} additional secondary outcomes\n"

        # Enhanced adverse events extraction grouped by organ system
        adverse_events_module = results_section.get('adverseEventsModule', {})
        serious_events = adverse_events_module.get('seriousEvents', [])
        if not isinstance(serious_events, list):
            serious_events = []
        other_events = adverse_events_module.get('otherEvents', [])
        if not isinstance(other_events, list):
            other_events = []
        
        adverse_events_text = ""
        if serious_events or other_events:
            if serious_events:
                # Group serious events by organ system
                serious_by_system = {}
                for event in serious_events:
                    term = event.get('term', 'N/A')
                    organ_system = event.get('organSystem', 'Other')
                    stats = event.get('stats', [])
                    total_affected = sum(stat.get('numAffected', 0) for stat in stats if isinstance(stat, dict))
                    total_at_risk = sum(stat.get('numAtRisk', 0) for stat in stats if isinstance(stat, dict))
                    
                    if organ_system not in serious_by_system:
                        serious_by_system[organ_system] = []
                    serious_by_system[organ_system].append(f"{term} ({total_affected}/{total_at_risk})")
                
                adverse_events_text += "\n**Serious Adverse Events by System:**\n"
                for system, events in serious_by_system.items():
                    adverse_events_text += f"\n**{system}:**\n"
                    for event in events[:5]:  # Limit to top 5 per system
                        adverse_events_text += f"- {event}\n"
                    if len(events) > 5:
                        adverse_events_text += f"- ... and {len(events)-5} more\n"
            
            if other_events:
                # Group common events by organ system (top 3 per system)
                common_by_system = {}
                for event in other_events:
                    term = event.get('term', 'N/A')
                    organ_system = event.get('organSystem', 'Other')
                    stats = event.get('stats', [])
                    total_affected = sum(stat.get('numAffected', 0) for stat in stats if isinstance(stat, dict))
                    total_at_risk = sum(stat.get('numAtRisk', 0) for stat in stats if isinstance(stat, dict))
                    
                    # Only include events affecting > 5% of patients
                    if total_at_risk > 0 and (total_affected / total_at_risk) > 0.05:
                        if organ_system not in common_by_system:
                            common_by_system[organ_system] = []
                        common_by_system[organ_system].append({
                            'term': term,
                            'affected': total_affected,
                            'at_risk': total_at_risk,
                            'rate': total_affected / total_at_risk
                        })
                
                # Sort by rate and take top events per system
                for system in common_by_system:
                    common_by_system[system].sort(key=lambda x: x['rate'], reverse=True)
                    common_by_system[system] = common_by_system[system][:3]
                
                if common_by_system:
                    adverse_events_text += "\n**Common Adverse Events by System (>5% incidence):**\n"
                    for system, events in common_by_system.items():
                        if events:  # Only show systems with events
                            adverse_events_text += f"\n**{system}:**\n"
                            for event in events:
                                rate_pct = event['rate'] * 100
                                adverse_events_text += f"- {event['term']}: {event['affected']}/{event['at_risk']} ({rate_pct:.1f}%)\n"
        else:
            adverse_events_text = "No adverse events reported in the structured API data."

        # Extract participant flow data for patient numbers
        participant_flow_text = ""
        if results_section:
            participant_flow_module = results_section.get('participantFlowModule', {})
            groups = participant_flow_module.get('groups', [])
            if groups:
                participant_flow_text += "**Participant Enrollment by Group:**\n"
                for group in groups:
                    group_title = group.get('title', 'N/A')
                    group_description = group.get('description', 'N/A')
                    participant_flow_text += f"- {group_title}: {group_description}\n"
                
                periods = participant_flow_module.get('periods', [])
                if periods:
                    for period in periods:
                        milestones = period.get('milestones', [])
                        for milestone in milestones:
                            if milestone.get('type') == 'STARTED':
                                participant_flow_text += "\n**Enrollment Numbers:**\n"
                                achievements = milestone.get('achievements', [])
                                for achievement in achievements:
                                    group_id = achievement.get('groupId', 'N/A')
                                    num_subjects = achievement.get('numSubjects', 'N/A')
                                    # Find corresponding group title
                                    group_title = next((g.get('title', 'N/A') for g in groups if g.get('id') == group_id), group_id)
                                    participant_flow_text += f"- {group_title}: {num_subjects} patients\n"
                                break
                        break
        
        # Extract sponsor and collaborator information
        sponsor_collaborators_module = protocol_section.get('sponsorCollaboratorsModule', {})
        lead_sponsor = sponsor_collaborators_module.get('leadSponsor', {})
        sponsor_name = lead_sponsor.get('name', 'N/A')
        sponsor_class = lead_sponsor.get('class', 'N/A')
        
        collaborators = sponsor_collaborators_module.get('collaborators', [])
        collaborator_text = ""
        if collaborators:
            collaborator_names = [collab.get('name', 'N/A') for collab in collaborators]
            collaborator_text = f"Collaborators: {', '.join(collaborator_names)}"
        
        sponsor_info = f"Lead Sponsor: {sponsor_name} ({sponsor_class})\n{collaborator_text}"
        
        # Extract contacts and locations for site information
        contacts_locations_module = protocol_section.get('contactsLocationsModule', {})
        locations = contacts_locations_module.get('locations', [])
        location_text = ""
        if locations:
            location_text += f"**Study Locations ({len(locations)} sites):**\n"
            # Group by country
            countries = {}
            for location in locations:
                country = location.get('country', 'Unknown')
                city = location.get('city', 'N/A')
                facility = location.get('facility', 'N/A')
                if country not in countries:
                    countries[country] = []
                countries[country].append(f"{facility}, {city}")
            
            for country, sites in countries.items():
                location_text += f"- {country}: {len(sites)} sites\n"
                # Show first few sites as examples
                for site in sites[:3]:
                    location_text += f"  • {site}\n"
                if len(sites) > 3:
                    location_text += f"  • ... and {len(sites)-3} more sites\n"
        
        # Extract basic demographic eligibility details
        eligibility_module = protocol_section.get('eligibilityModule', {})
        min_age = eligibility_module.get('minimumAge', 'N/A')
        max_age = eligibility_module.get('maximumAge', 'N/A')
        sex = eligibility_module.get('sex', 'N/A')
        healthy_volunteers = eligibility_module.get('healthyVolunteers', False)
        
        # Enhanced eligibility criteria processing
        def process_eligibility_criteria(eligibility_text):
            """Process eligibility criteria to separate inclusion and exclusion criteria"""
            if not eligibility_text or eligibility_text == 'N/A':
                return "No eligibility criteria available", [], []
            
            text = str(eligibility_text).strip()
            lines = text.split('\n')
            
            inclusion_criteria = []
            exclusion_criteria = []
            current_section = None
            
            inclusion_headers = ['inclusion criteria', 'inclusion', 'eligibility criteria', 'eligible participants']
            exclusion_headers = ['exclusion criteria', 'exclusion', 'excluded participants', 'exclusionary criteria']
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                line_lower = line.lower()
                
                if any(header in line_lower for header in inclusion_headers):
                    current_section = 'inclusion'
                    continue
                elif any(header in line_lower for header in exclusion_headers):
                    current_section = 'exclusion'
                    continue
                
                if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or 
                           line[0].isdigit() or line.startswith('o ')):
                    clean_line = line.strip()
                    
                    if clean_line.startswith('-'):
                        clean_line = clean_line[1:].strip()
                    elif clean_line.startswith('•'):
                        clean_line = clean_line[1:].strip()
                    elif clean_line.startswith('*'):
                        clean_line = clean_line[1:].strip()
                    elif clean_line[0].isdigit() and '. ' in clean_line[:5]:
                        period_index = clean_line.find('. ')
                        if period_index > 0 and period_index < 5:
                            clean_line = clean_line[period_index + 2:].strip()
                    
                    if len(clean_line) < 5:
                        continue
                    
                    if current_section == 'inclusion':
                        inclusion_criteria.append(clean_line)
                    elif current_section == 'exclusion':
                        exclusion_criteria.append(clean_line)
                    else:
                        if any(word in line_lower for word in ['must', 'should', 'required', 'age ≥', 'age >', 'performance status', 'confirmed', 'diagnosis']):
                            inclusion_criteria.append(clean_line)
                        elif any(word in line_lower for word in ['cannot', 'must not', 'prohibited', 'contraindicated', 'excluded']):
                            exclusion_criteria.append(clean_line)
                        else:
                            inclusion_criteria.append(clean_line)
                elif len(line) > 20 and current_section:
                    if current_section == 'inclusion':
                        inclusion_criteria.append(line)
                    elif current_section == 'exclusion':
                        exclusion_criteria.append(line)
            
            summary_parts = []
            if inclusion_criteria:
                key_inclusion = inclusion_criteria[:4]
                summary_parts.append(f"Key Inclusion: {'; '.join(key_inclusion[:2])}")
            
            if exclusion_criteria:
                key_exclusion = exclusion_criteria[:3]
                summary_parts.append(f"Key Exclusions: {'; '.join(key_exclusion[:2])}")
            
            summary = ". ".join(summary_parts) if summary_parts else "Standard eligibility criteria apply"
            
            return summary, inclusion_criteria, exclusion_criteria

        # Process eligibility criteria
        eligibility_criteria_summary, inclusion_list, exclusion_list = process_eligibility_criteria(eligibility_criteria)
        
        # Create detailed eligibility text
        detailed_eligibility = ""
        
        detailed_eligibility += f"**Demographics:** Age {min_age}"
        if max_age and max_age != 'N/A':
            detailed_eligibility += f" to {max_age}"
        detailed_eligibility += f", {sex}, Healthy volunteers: {'Yes' if healthy_volunteers else 'No'}\n\n"
        
        if inclusion_list:
            detailed_eligibility += "**Inclusion Criteria:**\n"
            for i, criterion in enumerate(inclusion_list[:8], 1):
                detailed_eligibility += f"{i}. {criterion}\n"
            if len(inclusion_list) > 8:
                detailed_eligibility += f"... and {len(inclusion_list)-8} additional inclusion criteria\n"
            detailed_eligibility += "\n"
        
        if exclusion_list:
            detailed_eligibility += "**Exclusion Criteria:**\n"
            for i, criterion in enumerate(exclusion_list[:8], 1):
                detailed_eligibility += f"{i}. {criterion}\n"
            if len(exclusion_list) > 8:
                detailed_eligibility += f"... and {len(exclusion_list)-8} additional exclusion criteria\n"
            detailed_eligibility += "\n"
        
        if not inclusion_list and not exclusion_list and eligibility_criteria != 'N/A':
            detailed_eligibility += "**Full Eligibility Criteria:**\n"
            if len(eligibility_criteria) > 800:
                detailed_eligibility += eligibility_criteria[:800] + "... [truncated]"
            else:
                detailed_eligibility += eligibility_criteria
        
        eligibility_comprehensive = f"{eligibility_criteria_summary}\n\n{detailed_eligibility.strip()}"

        # Structured data for section-wise summarization
        data_to_summarize = {
            "Study Overview": f"{official_title} | Status: {overall_status} | Type: {study_type} - {study_phase}",
            "Brief Description": brief_summary,
            "Primary and Secondary Objectives": outcomes_text if outcomes_text else None,
            "Treatment Arms and Interventions": f"{arm_groups_text}\n\n{interventions_text}" if (arm_groups_text or interventions_text) else None,
            "Eligibility Criteria": eligibility_comprehensive,
            "Enrollment and Participant Flow": participant_flow_text if participant_flow_text else None,
            "Adverse Events Profile": adverse_events_text if adverse_events_text and "No adverse events reported" not in adverse_events_text else None,
            "Study Locations": f"{len(locations)} sites across {len(set(loc.get('country', 'Unknown') for loc in locations))} countries" if locations else None,
            "Sponsor Information": sponsor_info if sponsor_info and sponsor_name != "N/A" else None
        }
        
        # Create parsed_json with proper field names (lowercase with underscores)
        # Preserve None values to accurately calculate metrics
        parsed_json = {
            "study_overview": data_to_summarize.get("Study Overview"),
            "brief_description": data_to_summarize.get("Brief Description"),
            "primary_secondary_objectives": data_to_summarize.get("Primary and Secondary Objectives"),
            "treatment_arms_interventions": data_to_summarize.get("Treatment Arms and Interventions"),
            "eligibility_criteria": data_to_summarize.get("Eligibility Criteria"),
            "enrollment_participant_flow": data_to_summarize.get("Enrollment and Participant Flow"),
            "adverse_events_profile": data_to_summarize.get("Adverse Events Profile"),
            "study_locations": data_to_summarize.get("Study Locations"),
            "sponsor_information": data_to_summarize.get("Sponsor Information")
        }
        
        state["data_to_summarize"] = data_to_summarize
        state["parsed_json"] = parsed_json
        
        # Calculate metrics based on parsed_json
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(parsed_json)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            state["error"] = f"Error: Study with NCT number was not found on ClinicalTrials.gov."
        else:
            state["error"] = f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        state["error"] = f"An error occurred while fetching the protocol: {e}"
    
    return state
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
        
        # Create data_to_summarize dict (same format as app_v1 - for display)
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
        
        # Create parsed_json with proper field names (lowercase with underscores)
        # Preserve None values to accurately calculate metrics
        parsed_json = {
            "study_overview": data_to_summarize.get("Study Overview"),
            "brief_description": data_to_summarize.get("Brief Description"),
            "primary_secondary_objectives": data_to_summarize.get("Primary and Secondary Objectives"),
            "treatment_arms_interventions": data_to_summarize.get("Treatment Arms and Interventions"),
            "eligibility_criteria": data_to_summarize.get("Eligibility Criteria"),
            "enrollment_participant_flow": data_to_summarize.get("Enrollment and Participant Flow"),
            "adverse_events_profile": data_to_summarize.get("Adverse Events Profile"),
            "study_locations": data_to_summarize.get("Study Locations"),
            "sponsor_information": data_to_summarize.get("Sponsor Information")
        }
        
        state["data_to_summarize"] = data_to_summarize
        state["parsed_json"] = parsed_json  # Use proper field names for metrics
        
        # Calculate metrics based on parsed_json
        state["confidence_score"], state["completeness_score"], state["missing_fields"] = calculate_metrics(parsed_json)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            state["error"] = f"Error: Study with NCT number was not found on ClinicalTrials.gov."
        else:
            state["error"] = f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        state["error"] = f"An error occurred while fetching the protocol: {e}"
    
    return state


def calculate_metrics(parsed_json: dict) -> tuple[float, float, list]:
    """Calculate confidence and completeness scores based on meaningful content"""
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
        
        # Check for meaningful content (not just "N/A" or short placeholders)
        if (content and 
            isinstance(content, str) and
            content.strip() != "N/A" and
            content.strip() != "" and
            "not available" not in content.lower() and
            "no data" not in content.lower() and
            len(content.strip()) > 30):  # Meaningful content threshold
            filled_fields += 1
            total_content += len(content)
        else:
            missing_fields.append(field)
    
    # Completeness: percentage of fields with meaningful data
    completeness_score = filled_fields / len(required_fields) if required_fields else 0.0
    
    # Confidence: based on average content richness per field
    if filled_fields > 0:
        avg_content_length = total_content / filled_fields
        # Scale confidence: 100 chars = 20%, 500 chars = 100%
        confidence_score = min(1.0, (avg_content_length - 100) / 400 + 0.2)
        confidence_score = max(0.0, confidence_score)  # Ensure non-negative
    else:
        confidence_score = 0.0
    
    return confidence_score, completeness_score, missing_fields


def check_quality(state: WorkflowState) -> Literal["llm_fallback", "chat_node"]:
    """Conditional edge: Check if LLM fallback is needed"""
    if state["confidence_score"] < 0.5 or state["completeness_score"] < 0.6:
        return "llm_fallback"
    else:
        return "chat_node"


def llm_fallback(state: WorkflowState) -> WorkflowState:
    """Node: Use LLM to extract missing fields from full document with chunking"""
    try:
        # Mark that LLM fallback is being used
        state["used_llm_fallback"] = True
        
        # Get full document text
        if state["input_type"] == "pdf":
            parser = EnhancedClinicalTrialParser()
            
            file_path = state["input_url"]
            # Handle URLs
            if file_path.startswith('http'):
                response = requests.get(file_path)
                temp_path = f"temp_llm_fallback.pdf"
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                file_path = temp_path
            
            # Extract full text using enhanced parser
            full_text, metadata = parser.extract_text_multimethod(file_path)
            
            # Clean up temp file
            if state["input_url"].startswith('http'):
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
        else:
            full_text = json.dumps(state["raw_data"], indent=2)
        
        # LLM extraction prompt
        system_prompt = """You are a clinical trial data extraction expert. 
Extract the following fields from the document chunk provided. 
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

Return as JSON. If a field is not found in this chunk, return null for that field."""

        # Chunk the document into 30k character chunks
        chunk_size = 30000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        # Process each chunk and merge results
        all_extracted = {}
        for i, chunk in enumerate(chunks):
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Document chunk {i+1}/{len(chunks)}:\n\n{chunk}")
            ]
            
            response = llm.invoke(messages)
            
            # Parse LLM response
            try:
                chunk_extracted = json.loads(response.content)
                # Merge non-null fields
                for field, value in chunk_extracted.items():
                    if value and value != "null" and (field not in all_extracted or not all_extracted.get(field)):
                        all_extracted[field] = value
            except json.JSONDecodeError:
                continue
        
        # Merge with existing data (only update missing or empty fields)
        for field, value in all_extracted.items():
            if value and (field not in state["parsed_json"] or not state["parsed_json"].get(field)):
                state["parsed_json"][field] = value
        
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
