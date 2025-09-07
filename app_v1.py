import streamlit as st
import openai
import requests
import re
import os
import sqlite3
import uuid
from fpdf import FPDF

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
        study_design = design_module.get('designInfo', {}).get('interventionModel', 'N/A')
        study_phase = ", ".join(design_module.get('phases', ['N/A']))
        
        # Interventions and Arm Groups
        arms_interventions_module = protocol_section.get('armsInterventionsModule', {})
        arm_groups_list = arms_interventions_module.get('armGroups', [])
        if not isinstance(arm_groups_list, list):
            arm_groups_list = []
        arm_groups_text = "\n".join([f"- ID: {ag.get('armGroupId', 'N/A')}\n  Title: {ag.get('armGroupLabel', 'N/A')}\n  Description: {ag.get('armGroupDescription', 'N/A')}" for ag in arm_groups_list])
        
        interventions_list = arms_interventions_module.get('interventions', [])
        if not isinstance(interventions_list, list):
            interventions_list = []
        interventions_text = "\n".join([f"- Name: {i.get('interventionName', 'N/A')}\n  Type: {i.get('interventionType', 'N/A')}" for i in interventions_list])

        # Eligibility Module
        eligibility_module = protocol_section.get('eligibilityModule', {})
        eligibility_criteria_data = eligibility_module.get('eligibilityCriteria', 'N/A')
        if isinstance(eligibility_criteria_data, dict):
            eligibility_criteria = eligibility_criteria_data.get('textblock', 'N/A')
        else:
            eligibility_criteria = eligibility_criteria_data
        
        # Outcomes Module
        outcomes_module = protocol_section.get('outcomesModule', {})
        outcomes_list = outcomes_module.get('primaryOutcomes', []) + outcomes_module.get('secondaryOutcomes', [])
        outcomes_text = "\n".join([f"- Measure: {o.get('outcomeMeasure', 'N/A')}\n  Description: {o.get('outcomeDescription', 'N/A')}" for o in outcomes_list])

        # Adverse Events (from resultsSection)
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
                adverse_events_text += "\n**Serious Adverse Events:**\n"
                for event in serious_events:
                    term = event.get('adverseEventTerm', 'N/A')
                    organ_system = event.get('adverseEventOrganSystem', 'N/A')
                    adverse_events_text += f"- Term: {term}, Organ System: {organ_system}\n"
            if other_events:
                adverse_events_text += "\n**Other Adverse Events:**\n"
                for event in other_events:
                    term = event.get('adverseEventTerm', 'N/A')
                    organ_system = event.get('adverseEventOrganSystem', 'N/A')
                    adverse_events_text += f"- Term: {term}, Organ System: {organ_system}\n"
        else:
            adverse_events_text = "No adverse events reported in the structured API data."

        # Structured data for section-wise summarization
        data_to_summarize = {
            "Official Title": official_title,
            "Overall Status": overall_status,
            "Study Type": study_type,
            "Study Design": study_design,
            "Study Phase": study_phase,
            "Brief Summary": brief_summary,
            "Detailed Description": detailed_description,
            "Study Arms and Treatment Plans": arm_groups_text if arm_groups_text else "No study arms or treatment plans available in the structured API data.",
            "Interventions": interventions_text if interventions_text else "No interventions available in the structured API data.",
            "Eligibility Criteria": eligibility_criteria,
            "Outcomes": outcomes_text if outcomes_text else "No outcomes available in the structured API data.",
            "Adverse Events": adverse_events_text
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
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_margins(10, 10, 10)
    
    # Add Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Clinical Protocol Summary for NCT ID: {nct_id}", ln=True, align='C')
    pdf.ln(5)

    # Add URL
    pdf.set_font("Arial", 'U', 10)
    url_text = f"https://clinicaltrials.gov/study/NCT{nct_id}"
    pdf.set_text_color(0, 0, 255) # Blue
    pdf.cell(0, 10, url_text, 0, 1, 'L', link=url_text)
    pdf.set_text_color(0, 0, 0) # Black
    pdf.ln(5)

    # Add Summary Content
    pdf.set_font("Arial", size=12)
    # This will handle markdown-style headers and bold text
    lines = summary_text.split('\n')
    for line in lines:
        if line.startswith('### **'):
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, line.replace('### **', '').replace('**', ''), ln=True)
            pdf.set_font("Arial", '', 12)
        elif line.startswith('**'):
            pdf.set_font("Arial", 'B', 12)
            pdf.write(5, line.replace('**', '') + " ")
            pdf.set_font("Arial", '', 12)
        else:
            pdf.write(5, line)
        
        if line.strip() == "":
            pdf.ln(5)

    return pdf.output(dest='S').encode('latin1')

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
                    initial_prompt = f"Please provide a concise summary of the following section from a clinical trial protocol:\n\n**Section:** {section}\n**Content:** {text_content}"
                    
                    messages_for_api = [
                        {"role": "system", "content": "You are a medical summarization assistant. Provide a concise and clear summary of the provided text, focusing on the key information for the given section. Do not invent information."},
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
            
        st.download_button(
            label="Download Summary as PDF",
            data=create_summary_pdf(full_summary, nct_id),
            file_name=f"clinical_trial_summary_{nct_id}.pdf",
            mime="application/pdf"
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
