import streamlit as st
import openai
import requests
import re
import os
import sqlite3
import uuid

# Set up the OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Define the database file
DB_FILE = "chat_history.db"

# --- Database Helper Functions ---

def init_db():
    """Initializes the SQLite database and creates a chat_messages table."""
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
    conn.close()

def save_message_to_db(conversation_id, role, content):
    """Saves a single message to the database with a conversation ID."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)", (conversation_id, role, content))
    conn.commit()
    conn.close()

def load_messages_from_db(conversation_id):
    """Loads all chat messages for a specific conversation ID."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

def get_all_conversations():
    """Returns a list of all unique conversation IDs in the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT conversation_id FROM chat_messages ORDER BY id DESC")
    conversations = [row[0] for row in c.fetchall()]
    conn.close()
    return conversations

# --- Main App Logic ---

def get_protocol_text(nct_number):
    try:
        # Use requests to directly access the ClinicalTrials.gov API v2.0
        api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_number}"
        response = requests.get(api_url)
        response.raise_for_status()  # This will raise an HTTPError if the status code is 4xx or 5xx
        
        study_data = response.json()
        
        # Check if the study was found
        if 'protocolSection' not in study_data:
            return None, "Error: Study data could not be found for this NCT number."

        study = study_data['protocolSection']
        
        nct_id = study['identificationModule'].get('nctId', 'N/A')
        official_title = study['identificationModule'].get('officialTitle', 'N/A')
        brief_summary = study['descriptionModule'].get('briefSummary', 'N/A')
        detailed_description = study['descriptionModule'].get('detailedDescription', 'N/A')
        
        protocol_text = f"**NCT ID:** {nct_id}\n\n**Official Title:** {official_title}\n\n**Brief Summary:**\n{brief_summary}\n\n**Detailed Description:**\n{detailed_description}"
        return protocol_text, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, f"Error: Study with NCT number {nct_number} was not found on ClinicalTrials.gov."
        return None, f"HTTP error occurred while fetching the protocol: {e}"
    except Exception as e:
        return None, f"An error occurred while fetching the protocol: {e}"

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

# --- Streamlit UI and Chat Management ---

# Initialize the database on startup
init_db()

# Check for rerun flag at the top of the script
if "rerun_flag" in st.session_state and st.session_state.rerun_flag:
    st.session_state.rerun_flag = False
    st.rerun()

st.title("Clinical Trial Protocol Summarizer Chatbot (SQLite)")

st.sidebar.header("Past Chats")
conversations = get_all_conversations()
for convo_id in conversations:
    if st.sidebar.button(convo_id, key=convo_id):
        st.session_state.messages = load_messages_from_db(convo_id)
        st.session_state.current_convo_id = convo_id

if st.sidebar.button("Start New Chat", key="new_chat_button"):
    st.session_state.messages = []
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4()) # Added to reset the URL input
    st.session_state.rerun_flag = True

st.markdown("Enter a ClinicalTrials.gov URL to start a conversation about the study.")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_convo_id" not in st.session_state:
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4()) # Initialize the URL key

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
    
    protocol_text, fetch_error = get_protocol_text(nct_number)

    if fetch_error:
        st.error(fetch_error)
    elif protocol_text:
        initial_prompt = f"Please summarize the following clinical trial protocol and be ready to answer follow-up questions about it:\n\n{protocol_text}"
        
        st.session_state.messages.append({"role": "user", "content": f"URL: {url_input}"})
        with st.chat_message("user"):
            st.markdown(f"URL: {url_input}")
        save_message_to_db(st.session_state.current_convo_id, "user", f"URL: {url_input}")
            
        st.success("Protocol details fetched successfully! Generating summary...")
        
        with st.spinner("Summarizing protocol with GPT-4o..."):
            messages_for_api = [
                {"role": "system", "content": "You are a medical summarization assistant. Provide a concise and clear summary of a clinical trial protocol, highlighting the study's purpose, design, interventions, and key outcomes. After the initial summary, answer follow-up questions based on the provided protocol text. Do not invent information."},
                {"role": "user", "content": initial_prompt}
            ]
            summary, summary_error = summarize_with_gpt4o(messages_for_api)

        if summary_error:
            st.error(summary_error)
        else:
            st.session_state.messages.append({"role": "assistant", "content": summary})
            with st.chat_message("assistant"):
                st.markdown(summary)
            
            with st.expander("See Original Protocol Text"):
                st.text(protocol_text)
            
            save_message_to_db(st.session_state.current_convo_id, "assistant", summary)
            
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
