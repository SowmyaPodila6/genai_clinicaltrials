import streamlit as st
import openai
import requests
import json
import re
import os
import sqlite3
import uuid
from fpdf import FPDF
from clinical_trail_parser import ClinicalTrialPDFParser

# Set up the OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# --- Database Helper Functions ---

def get_db_path():
    """
    Gets the unique database path for the current user session.
    This ensures that each session has its own isolated database file.
    """
    if "db_path" not in st.session_state:
        st.session_state.db_path = f"chat_history_{st.session_state.current_convo_id}.db"
    return st.session_state.db_path

def get_db_connection():
    """Connects to the session-specific database and ensures the table exists."""
    conn = sqlite3.connect(get_db_path())
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
    """Saves a single message to the session-specific database."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)", (conversation_id, role, content))
    conn.commit()
    conn.close()

def load_messages_from_db(conversation_id):
    """Loads all chat messages for the specific conversation ID from the session-specific database."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

# --- Clinical Trials API Logic ---

def get_protocol_data(nct_number):
    """
    Fetches the full JSON data for a clinical trial from the ClinicalTrials.gov API.
    """
    try:
        api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_number}"
        response = requests.get(api_url)
        response.raise_for_status()
        
        study_data = response.json()
        
        if 'protocolSection' not in study_data:
            return None, f"Error: Study data could not be found for NCT number {nct_number}."

        return study_data, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, f"Error: Study with NCT number {nct_number} was not found on ClinicalTrials.gov."
        return None, f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        return None, f"An error occurred while fetching the protocol: {e}"

# --- LLM and Prompt Logic ---

def create_mock_summary_prompt(json_data):
    """
    Creates a detailed system prompt for the LLM to guide the summarization
    based on the Mock Clinical Trial Summary document.
    """
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
    
    prompt = f"Summarize the following clinical trial JSON data using the provided template.\n\nJSON Data:\n{json.dumps(json_data, indent=2)}\n\nTemplate:\n{mock_summary_template}"
    
    return prompt

def summarize_with_gpt4o(messages):
    """Summarizes text using the GPT-4o model."""
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

# --- Streamlit UI and Chat Management ---

def new_chat_click():
    st.session_state.messages = []
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())
    st.rerun()

st.title("Gen AI-Powered Clinical Protocol Summarizer v4")
st.markdown("Enter a ClinicalTrials.gov URL or upload a PDF document to get a formatted summary of the study.")

# Sidebar with new chat button
with st.sidebar:
    st.markdown("### Chat Controls")
    if st.button("🔄 New Chat", type="primary"):
        new_chat_click()
    
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("1. **URL Tab**: Enter a ClinicalTrials.gov URL to fetch and summarize study data")
    st.markdown("2. **PDF Tab**: Upload a clinical trial PDF document to parse and analyze")
    st.markdown("3. Ask follow-up questions about the study or document")

def handle_url_input():
    """Handle the URL input functionality."""
    # Handle the initial URL input
    url_input = st.text_input("ClinicalTrials.gov URL:", placeholder="e.g., https://clinicaltrials.gov/study/NCT01234567", key=st.session_state.url_key)

    nct_match = re.search(r"NCT\d{8}", url_input)

    if url_input and nct_match and not st.session_state.messages:
        nct_number = nct_match.group(0)
        st.info(f"Found NCT number: **{nct_number}**. Fetching full protocol JSON...")
        
        json_data, fetch_error = get_protocol_data(nct_number)

        if fetch_error:
            st.error(fetch_error)
        elif json_data:
            st.session_state.messages.append({"role": "user", "content": f"URL: {url_input}"})
            with st.chat_message("user"):
                st.markdown(f"URL: {url_input}")
            save_message_to_db(st.session_state.current_convo_id, "user", f"URL: {url_input}")
                
            st.success("Protocol JSON fetched successfully! Generating summary...")
            
            with st.spinner("Summarizing protocol with GPT-4o..."):
                initial_prompt = create_mock_summary_prompt(json_data)
                
                messages_for_api = [
                    {"role": "system", "content": "You are a medical summarization assistant. Provide a concise and clear summary of the provided JSON data, formatted exactly like the example provided in the prompt. Do not invent information. If a section's information is not present, state that it is not available."},
                    {"role": "user", "content": initial_prompt}
                ]
                
                summary, summary_error = summarize_with_gpt4o(messages_for_api)

            if summary_error:
                st.error(summary_error)
            else:
                st.session_state.messages.append({"role": "assistant", "content": summary})
                with st.chat_message("assistant"):
                    st.markdown(summary)
                
                save_message_to_db(st.session_state.current_convo_id, "assistant", summary)

def handle_pdf_upload():
    """Handle the PDF upload and parsing functionality."""
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        st.info(f"Uploaded: **{uploaded_file.name}** ({uploaded_file.size} bytes)")
        
        with st.spinner("Parsing PDF document..."):
            try:
                # Parse PDF
                parser = ClinicalTrialPDFParser()
                pdf_bytes = uploaded_file.read()
                sections = parser.parse_pdf_bytes(pdf_bytes)
                
                # Map to strict 9-field schema
                from clinical_trail_parser import map_sections_to_schema
                parsed_schema = map_sections_to_schema(sections)
                
                # Store parsed sections in session state for follow-up questions
                st.session_state.parsed_sections = parsed_schema
                
                # Add upload notification to chat
                st.session_state.messages.append({"role": "user", "content": f"Uploaded PDF: {uploaded_file.name}"})
                save_message_to_db(st.session_state.current_convo_id, "user", f"Uploaded PDF: {uploaded_file.name}")
                
                # Show confirmation message
                confirmation_msg = f"✅ **PDF uploaded and parsed successfully!**\n\n**Document:** {uploaded_file.name}\n\n**Fields parsed:**\n"
                for field in parsed_schema.keys():
                    has_content = bool(parsed_schema[field].strip())
                    status = "✓" if has_content else "✗"
                    confirmation_msg += f"- {status} {field}\n"
                
                confirmation_msg += "\n**What would you like to do?**\n- Ask specific questions about the document\n- Request a full summary\n- Ask about particular sections"
                
                st.session_state.messages.append({"role": "assistant", "content": confirmation_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", confirmation_msg)
                
                st.success("PDF parsed successfully! Ask questions or request a summary in the chat below.")
                
            except Exception as e:
                error_msg = f"Error parsing PDF: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)

# Add tabs for different input methods
tab1, tab2 = st.tabs(["ClinicalTrials.gov URL", "PDF Upload"])

with tab1:
    st.markdown("### Enter ClinicalTrials.gov URL")
    handle_url_input()

with tab2:
    st.markdown("### Upload PDF Document")
    handle_pdf_upload()

# The "Past Chats" functionality is no longer available to prevent database concurrency issues.
# Each user session will now have a fresh, isolated conversation.

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_convo_id" not in st.session_state:
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())

if "parsed_sections" not in st.session_state:
    st.session_state.parsed_sections = None

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle follow-up chat input
if prompt := st.chat_input("Ask a follow-up question about the study or document..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    save_message_to_db(st.session_state.current_convo_id, "user", prompt)

    # Prepare context for the API call
    system_content = "You are a medical summarization assistant. Answer questions based on the provided protocol text or document sections. Do not invent information."
    
    # If we have parsed PDF sections, include them in the context
    if st.session_state.parsed_sections:
        sections_text = "\n\n".join([f"**{section}:**\n{content}" for section, content in st.session_state.parsed_sections.items()])
        system_content += f"\n\nDocument sections for reference:\n{sections_text}"

    messages_for_api = [
        {"role": "system", "content": system_content},
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
