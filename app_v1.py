
import streamlit as st
import openai
import requests
import re
import os
import sqlite3
import uuid
from fpdf import FPDF

# --- Mock Summary Template ---
mock_summary_template = """
Below is an example of a desired summary format for a clinical trial protocol:

1. Summary
Title: A Phase 1/2 Study of Agent X (NSC ######) in Combination with Agent Y in Patients with Advanced Non-Small Cell Lung Cancer (NSCLC)
Design: Phase 1 - Dose-escalation; Phase 2 - Expansion to assess efficacy.
Primary Objective (Phase 1): Determine MTD and recommended Phase 2 dose (RP2D).
Primary Objective (Phase 2): Objective response rate (ORR) per RECIST v1.1.
Secondary Objectives: PFS, OS, safety, symptom relief, biomarker analysis.
Eligibility: Adults 18 and older, ECOG 0-1, measurable disease, archival & fresh biopsy optional/required.

2. Historical Submissions with Similar Drugs
(Note: This information is not always available in the standard ClinicalTrials.gov JSON. Please state if no such data can be found.)
Protocol ID | Agents Studied | Disease | Phase | Outcome
NCI-2021-101 | Agent X (mono) | Colorectal | 1 | Grade 3 diarrhea at 100 mg/m2
... (provide a table if historical data exists in the provided JSON)

3. Potential Adverse Events
System | Common AEs | Serious AEs
GI | Nausea, diarrhea | Colitis, perforation
Hematologic | Anemia, neutropenia | Febrile neutropenia
... (provide a table based on the provided JSON data)

4. Treatment Plan Overview
Phase 1 Arms:
Arm | Dose Level | Agent X (mg/m2) | Agent Y (mg) | Patients
A | DL1 | 50 | 100 | 3-6
... (provide a table based on the provided JSON data)
Phase 2 Expansion:
Arm | Agent X | Agent Y | Patients | Objective
1 | 75 mg/m2 | 200 mg | 25 | ORR
... (provide a table based on the provided JSON data)

Please use the provided JSON data from a clinical trial to generate a summary that follows this exact format.
Extract the relevant information and fill in the sections.
"""

# Set up the OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Define the database file
DB_FILE = "chat_history.db"

# --- Database Helper Functions ---

# Connects to the database and ensures the table exists
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn

def save_message_to_db(conversation_id, role, content):
    """Saves a single message to the database with a conversation ID."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)", (conversation_id, role, content))
    conn.commit()
    conn.close()

def load_messages_from_db(conversation_id):
    """Loads all chat messages for a specific conversation ID."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

def get_all_conversations():
    """Returns a list of all unique conversation IDs in the database."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT conversation_id FROM chat_messages ORDER BY id DESC")
    conversations = [row[0] for row in c.fetchall()]
    conn.close()
    return conversations

# --- App Logic ---

def get_protocol_data(nct_number):
    try:
        api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_number}"
        response = requests.get(api_url)
        response.raise_for_status()
        
        study_data = response.json()
        
        protocol_section = study_data.get('protocolSection', {})
        results_section = study_data.get('resultsSection', {})
        
        if not protocol_section:
            return None, None, "Error: Study data could not be found for this NCT number."

        # Identification Module
        identification_module = protocol_section.get('identificationModule', {})
        nct_id = identification_module.get('nctId', 'N/A')
        official_title = identification_module.get('officialTitle', 'N/A')

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
        
        # Extract additional eligibility details
        eligibility_module = protocol_section.get('eligibilityModule', {})
        min_age = eligibility_module.get('minimumAge', 'N/A')
        max_age = eligibility_module.get('maximumAge', 'N/A')
        sex = eligibility_module.get('sex', 'N/A')
        healthy_volunteers = eligibility_module.get('healthyVolunteers', False)
        std_ages = eligibility_module.get('stdAges', [])
        
        eligibility_summary = f"Age: {min_age}"
        if max_age and max_age != 'N/A':
            eligibility_summary += f" to {max_age}"
        eligibility_summary += f"\nSex: {sex}\nHealthy Volunteers: {'Yes' if healthy_volunteers else 'No'}"
        if std_ages:
            eligibility_summary += f"\nAge Groups: {', '.join(std_ages)}"
        
        # Extract conditions/diseases studied
        conditions_module = protocol_section.get('conditionsModule', {})
        conditions = conditions_module.get('conditions', [])
        keywords = conditions_module.get('keywords', [])
        
        conditions_text = ""
        if conditions:
            conditions_text += f"Conditions: {', '.join(conditions)}\n"
        if keywords:
            conditions_text += f"Keywords: {', '.join(keywords)}"
        
        # Historical submissions note
        historical_note = "Historical Submissions with Similar Drugs: This information is not available in the standard ClinicalTrials.gov JSON data structure."

        # Structured data for section-wise summarization
        data_to_summarize = {
            "Official Title": official_title,
            "Overall Status": overall_status,
            "Study Type and Phase": f"{study_type} - {study_phase}",
            "Study Design Details": study_design_text,
            "Conditions and Keywords": conditions_text if conditions_text else "No conditions specified",
            "Brief Summary": brief_summary,
            "Detailed Description": detailed_description,
            "Sponsor Information": sponsor_info,
            "Study Locations": location_text if location_text else "No location information available",
            "Eligibility Summary": eligibility_summary,
            "Detailed Eligibility Criteria": eligibility_criteria,
            "Study Arms and Treatment Plans": arm_groups_text if arm_groups_text else "No study arms or treatment plans available in the structured API data.",
            "Interventions and Agents": interventions_text if interventions_text else "No interventions available in the structured API data.",
            "Participant Flow and Enrollment": participant_flow_text if participant_flow_text else "No participant flow data available",
            "Primary and Secondary Outcomes": outcomes_text if outcomes_text else "No outcomes available in the structured API data.",
            "Adverse Events Profile": adverse_events_text,
            "Historical Submissions": historical_note
        }

        return data_to_summarize, nct_id, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, None, f"Error: Study with NCT number {nct_number} was not found on ClinicalTrials.gov."
        return None, None, f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        return None, None, f"An error occurred while fetching the protocol: {e}"

def summarize_with_gpt4o(messages):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()
        return summary, None
    except openai.APIError as e:
        return None, f"OpenAI API Error: {e}"
    except Exception as e:
        return None, f"An unexpected error occurred during summarization: {e}"

def create_summary_pdf(summary_text, nct_id):
    try:
        from fpdf import FPDF
        import unicodedata
        
        # Function to clean text for PDF
        def clean_text_for_pdf(text):
            if not text:
                return ""
            # Remove or replace problematic Unicode characters
            # Convert to ASCII, replacing non-ASCII chars
            try:
                # First try to encode/decode to remove problematic characters
                cleaned = text.encode('ascii', 'ignore').decode('ascii')
                return cleaned
            except:
                # If that fails, use unicodedata to normalize
                normalized = unicodedata.normalize('NFKD', text)
                ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
                return ascii_text
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.set_margins(10, 10, 10)
        
        # Add Title
        pdf.set_font("Arial", 'B', 16)
        title_text = clean_text_for_pdf(f"Clinical Protocol Summary for NCT ID: {nct_id}")
        pdf.cell(200, 10, txt=title_text, ln=True, align='C')
        pdf.ln(5)

        # Add URL
        pdf.set_font("Arial", 'U', 10)
        url_text = f"https://clinicaltrials.gov/study/{nct_id}"
        pdf.set_text_color(0, 0, 255) # Blue
        pdf.cell(0, 10, url_text, 0, 1, 'L', link=url_text)
        pdf.set_text_color(0, 0, 0) # Black
        pdf.ln(5)

        # Add Summary Content
        pdf.set_font("Arial", size=12)
        
        # Clean the summary text first
        clean_summary = clean_text_for_pdf(summary_text)
        
        # Handle markdown-style headers and bold text
        lines = clean_summary.split('\n')
        for line in lines:
            try:
                if line.startswith('### **'):
                    pdf.set_font("Arial", 'B', 14)
                    header_text = clean_text_for_pdf(line.replace('### **', '').replace('**', ''))
                    if len(header_text) > 50:  # Truncate very long headers
                        header_text = header_text[:47] + "..."
                    pdf.cell(0, 10, header_text, ln=True)
                    pdf.set_font("Arial", '', 12)
                elif line.startswith('**'):
                    pdf.set_font("Arial", 'B', 12)
                    bold_text = clean_text_for_pdf(line.replace('**', '') + " ")
                    pdf.write(5, bold_text)
                    pdf.set_font("Arial", '', 12)
                else:
                    line_text = clean_text_for_pdf(line)
                    if line_text.strip():  # Only write non-empty lines
                        pdf.write(5, line_text)
                
                if line.strip() == "":
                    pdf.ln(5)
            except Exception as e:
                # Skip problematic lines and continue
                continue

        return pdf.output(dest='S').encode('latin1', 'ignore')
        
    except Exception as e:
        # If PDF creation fails, return a simple error PDF
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, "PDF Generation Error", ln=True)
            pdf.cell(0, 10, f"NCT ID: {nct_id}", ln=True)
            pdf.cell(0, 10, "Please download the summary as text instead.", ln=True)
            return pdf.output(dest='S').encode('latin1', 'ignore')
        except:
            # Return minimal bytes if everything fails
            return b"PDF generation failed due to encoding issues."

# --- Streamlit UI and Chat Management ---

def new_chat_click():
    st.session_state.messages = []
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())
    st.rerun()

st.title("Gen AI-Powered Clinical Protocol Summarizer")
st.markdown("Enter a ClinicalTrials.gov URL below to get a section-by-section summary of the study. You can then ask follow-up questions about the protocol.")

st.sidebar.header("Past Chats")
conversations = get_all_conversations()
for convo_id in conversations:
    if st.sidebar.button(convo_id, key=convo_id):
        st.session_state.messages = load_messages_from_db(convo_id)
        st.session_state.current_convo_id = convo_id
        st.rerun()

st.sidebar.button("Start New Chat", key="new_chat_button", on_click=new_chat_click)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_convo_id" not in st.session_state:
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle the initial URL input
url_input = st.text_input("ClinicalTrials.gov URL:", placeholder="e.g., https://clinicaltrials.gov/study/NCT01234567", key=st.session_state.url_key)

nct_match = re.search(r"NCT\d{8}", url_input)

if url_input and nct_match and not st.session_state.messages:
    nct_number = nct_match.group(0)
    st.info(f"Found NCT number: **{nct_number}**. Fetching protocol details...")
    
    data_to_summarize, nct_id, fetch_error = get_protocol_data(nct_number)

    if fetch_error:
        st.error(fetch_error)
    elif data_to_summarize:
        st.session_state.messages.append({"role": "user", "content": f"URL: {url_input}"})
        with st.chat_message("user"):
            st.markdown(f"URL: {url_input}")
        save_message_to_db(st.session_state.current_convo_id, "user", f"URL: {url_input}")
            
        st.success("Protocol details fetched successfully! Generating summary...")
        
        full_summary = ""
        for section, text_content in data_to_summarize.items():
            if text_content and text_content not in ["No study arms or treatment plans available in the structured API data.", "No interventions available in the structured API data.", "No outcomes available in the structured API data.", "No adverse events reported in the structured API data."]:
                with st.spinner(f"Summarizing '{section}'..."):
                    initial_prompt = f"""Please provide a comprehensive summary of the following section from a clinical trial protocol. Follow the structure and format shown in the template below as closely as possible:

{mock_summary_template}

**Section:** {section}
**Content:** {text_content}

INSTRUCTIONS:
1. Extract and organize the relevant information from the content
2. Present it in a structured format similar to the template
3. Create tables where appropriate (use markdown table format)
4. For treatment plans, extract dose levels, patient numbers, and objectives
5. For adverse events, group by organ system and show incidence rates
6. For objectives, clearly distinguish between safety and efficacy endpoints
7. If specific information is not available in the content, note that it is not available rather than making it up
8. Pay special attention to:
   - Dose escalation schemes and dose levels
   - Patient enrollment numbers per arm
   - MTD and RP2D information
   - RECIST criteria and response rates
   - ECOG performance status requirements
   - Biomarker analysis plans

Format tables using proper markdown syntax with clear headers and organized data."""
                    messages_for_api = [
                        {"role": "system", "content": "You are a medical summarization assistant specializing in clinical trial protocols. You excel at extracting and organizing complex clinical data into clear, structured summaries. Focus on creating well-formatted tables for treatment plans, adverse events, and study arms. Always distinguish between Phase 1 safety objectives (MTD/RP2D) and Phase 2 efficacy objectives (ORR, PFS, OS). Present adverse events grouped by organ system with incidence rates. Extract dose information, patient numbers, and enrollment details accurately. Use markdown formatting for tables and clear section headers. Do not invent information that is not present in the source material."},
                        {"role": "user", "content": initial_prompt}
                    ]
                    section_summary, summary_error = summarize_with_gpt4o(messages_for_api)

                if summary_error:
                    st.error(summary_error)
                    full_summary += f"### **{section}**\n\n_Summary failed due to an error._\n\n"
                else:
                    full_summary += f"### **{section}**\n\n{section_summary}\n\n"
            else:
                full_summary += f"### **{section}**\n\n{text_content}\n\n"
        
        st.session_state.messages.append({"role": "assistant", "content": full_summary})
        with st.chat_message("assistant"):
            st.markdown(full_summary)
        
        # Provide both PDF and text download options
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                pdf_data = create_summary_pdf(full_summary, nct_id)
                st.download_button(
                    label="📄 Download Summary as PDF",
                    data=pdf_data,
                    file_name=f"clinical_trial_summary_{nct_id}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF generation failed: {str(e)}")
        
        with col2:
            # Provide text download as backup
            text_summary = f"Clinical Protocol Summary for NCT ID: {nct_id}\n"
            text_summary += f"URL: https://clinicaltrials.gov/study/{nct_id}\n\n"
            text_summary += full_summary
            
            st.download_button(
                label="📝 Download Summary as Text",
                data=text_summary.encode('utf-8'),
                file_name=f"clinical_trial_summary_{nct_id}.txt",
                mime="text/plain"
            )
        
        if nct_id and nct_id != 'N/A':
            st.markdown(f"**<a href='https://clinicaltrials.gov/study/{nct_id}' target='_blank'>View Full Protocol on ClinicalTrials.gov</a>**", unsafe_allow_html=True)
        else:
            st.markdown("Could not generate a link to the full protocol.")
        
        save_message_to_db(st.session_state.current_convo_id, "assistant", full_summary)
            
# Handle follow-up chat input
if prompt := st.chat_input("Ask a follow-up question about the study..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    save_message_to_db(st.session_state.current_convo_id, "user", prompt)

    messages_for_api = [
        {"role": "system", "content": "You are a medical summarization assistant. Answer questions based on the provided protocol text. Do not invent information."},
    ]
    messages_for_api.extend(st.session_state.messages)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response, summary_error = summarize_with_gpt4o(messages_for_api)
            if summary_error:
                st.error(summary_error)
                st.session_state.messages.append({"role": "assistant", "content": "Sorry, an error occurred."})
            else:
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                save_message_to_db(st.session_state.current_convo_id, "assistant", response)
