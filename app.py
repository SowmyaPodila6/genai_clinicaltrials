import streamlit as st
import openai
from pytrials.client import ClinicalTrials
import re
import os
import sqlite3

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
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_message_to_db(role, content):
    """Saves a single message to the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def load_messages_from_db():
    """Loads all chat messages from the database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages ORDER BY id")
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

# --- Main App Logic ---

def get_protocol_text(nct_number):
    try:
        ct = ClinicalTrials()
        # Updated to use valid fields for the JSON format
        study_fields = ct.get_study_fields(
            search_expr=f"NCTId:{nct_number}",
            fields=["NCTId", "OfficialTitle", "BriefSummary", "DetailedDescription"],
            max_studies=1,
            fmt="json"
        )
        if not study_fields:
            return None, "Error: Could not retrieve study data for this NCT number."
        study_data = study_fields[0]
        nct_id = study_data.get('NCTId')
        official_title = study_data.get('OfficialTitle')
        brief_summary = study_data.get('BriefSummary')
        detailed_description = study_data.get('DetailedDescription')
        
        protocol_text = f"**NCT ID:** {nct_id}\n\n**Official Title:** {official_title}\n\n**Brief Summary:**\n{brief_summary}\n\n**Detailed Description:**\n{detailed_description}"
        return protocol_text, None
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

st.title("Clinical Trial Protocol Summarizer Chatbot (SQLite)")
st.markdown("Enter a ClinicalTrials.gov URL to start a conversation about the study.")

# Initialize chat history by loading from the database
if "messages" not in st.session_state:
    st.session_state.messages = load_messages_from_db()

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle the initial URL input
url_input = st.text_input("ClinicalTrials.gov URL:", placeholder="e.g., https://clinicaltrials.gov/study/NCT01234567")

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
        save_message_to_db("user", f"URL: {url_input}") # Save to DB
            
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
            
            save_message_to_db("assistant", summary) # Save to DB
            
# Handle follow-up chat input
if prompt := st.chat_input("Ask a follow-up question about the study..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    save_message_to_db("user", prompt) # Save to DB

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
                
                save_message_to_db("assistant", response) # Save to DB
