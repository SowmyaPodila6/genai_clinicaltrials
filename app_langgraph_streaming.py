"""
Streamlit App with LangGraph Workflow Integration
Streaming Chatbot - Following app_v1.py structure
"""

import streamlit as st
import json
import uuid
import sqlite3
from langgraph_workflow import build_workflow, chat_node_stream
from dotenv import load_dotenv
import re

load_dotenv()

# Database functions (same as app_v1)
DB_FILE = "chat_history.db"

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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)", 
              (conversation_id, role, content))
    conn.commit()
    conn.close()

def load_messages_from_db(conversation_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id", 
              (conversation_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages

def get_all_conversations():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT conversation_id FROM chat_messages ORDER BY id DESC")
    conversations = [row[0] for row in c.fetchall()]
    conn.close()
    return conversations

def new_chat_click():
    st.session_state.messages = []
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())
    st.session_state.current_state = None
    st.rerun()

# Page configuration
st.set_page_config(
    page_title="Clinical Trial Analysis - LangGraph",
    page_icon="🔬",
    layout="wide"
)

# Initialize session state
if "workflow_app" not in st.session_state:
    st.session_state.workflow_app = build_workflow()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_convo_id" not in st.session_state:
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())

if "current_state" not in st.session_state:
    st.session_state.current_state = None

# Title
st.title("🔬 Gen AI-Powered Clinical Protocol Summarizer")
st.markdown("**LangGraph Workflow Edition** | Enter a ClinicalTrials.gov URL or upload a PDF document")

# Sidebar
st.sidebar.header("Past Chats")
conversations = get_all_conversations()
for convo_id in conversations:
    if st.sidebar.button(convo_id, key=f"conv_{convo_id}"):
        st.session_state.messages = load_messages_from_db(convo_id)
        st.session_state.current_convo_id = convo_id
        # Restore state if available
        for msg in st.session_state.messages:
            if msg["role"] == "assistant" and "Clinical Trial Summary" in msg["content"]:
                nct_match = re.search(r"NCT\d{8}", msg["content"])
                if nct_match:
                    st.session_state.current_summary = msg["content"]
                break
        st.rerun()

st.sidebar.button("Start New Chat", key="new_chat_button", on_click=new_chat_click)

# Show metrics in sidebar if state exists
if st.session_state.current_state:
    st.sidebar.divider()
    st.sidebar.header("📊 Extraction Metrics")
    
    state = st.session_state.current_state
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        confidence = state.get("confidence_score", 0)
        st.metric(
            "Confidence", 
            f"{confidence:.1%}",
            delta="High" if confidence > 0.7 else "Low"
        )
    with col2:
        completeness = state.get("completeness_score", 0)
        st.metric(
            "Completeness", 
            f"{completeness:.1%}",
            delta="Good" if completeness > 0.8 else "Incomplete"
        )
    
    missing = state.get("missing_fields", [])
    if missing:
        st.sidebar.warning(f"**Missing {len(missing)} fields:**")
        for field in missing[:5]:
            st.sidebar.write(f"• {field.replace('_', ' ').title()}")
    else:
        st.sidebar.success("✅ All fields extracted!")
    
    # Download button
    if state.get("parsed_json"):
        st.sidebar.divider()
        json_str = json.dumps(state["parsed_json"], indent=2)
        st.sidebar.download_button(
            "📄 Download JSON",
            json_str,
            file_name=f"clinical_trial_{state.get('nct_id', 'data')}.json",
            mime="application/json",
            use_container_width=True
        )

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Tabs for input (same as app_v1)
tab1, tab2 = st.tabs(["🌐 ClinicalTrials.gov URL", "📄 PDF Upload"])

with tab1:
    st.markdown("### Enter ClinicalTrials.gov URL")
    url_input = st.text_input(
        "ClinicalTrials.gov URL:", 
        placeholder="e.g., https://clinicaltrials.gov/study/NCT01234567", 
        key=st.session_state.url_key
    )
    nct_match = re.search(r"NCT\d{8}", url_input) if url_input else None

with tab2:
    st.markdown("### Upload PDF Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf_upload")

# Handle initial URL input
if url_input and nct_match and not st.session_state.messages:
    nct_number = nct_match.group(0)
    st.info(f"Found NCT number: **{nct_number}**. Processing through LangGraph workflow...")
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": f"URL: {url_input}"})
    with st.chat_message("user"):
        st.markdown(f"URL: {url_input}")
    save_message_to_db(st.session_state.current_convo_id, "user", f"URL: {url_input}")
    
    # Run workflow
    with st.spinner("Extracting data from ClinicalTrials.gov..."):
        try:
            initial_state = {
                "input_url": url_input,
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
            }
            
            # Process through workflow (non-streaming for initial extraction)
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {result['error']}"})
                save_message_to_db(st.session_state.current_convo_id, "assistant", f"Error: {result['error']}")
            else:
                st.session_state.current_state = result
                st.success("✅ Data extracted successfully! Generating summary...")
                
                # Stream the summary
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    # Use streaming function
                    for chunk in chat_node_stream(result):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                
                # Save to database
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
                
                st.balloons()
                st.rerun()
                
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)

# Handle PDF upload
if uploaded_file is not None and not st.session_state.messages:
    st.info(f"Uploaded: **{uploaded_file.name}** ({uploaded_file.size} bytes)")
    
    # Save temporarily
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.getvalue())
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": f"Uploaded PDF: {uploaded_file.name}"})
    with st.chat_message("user"):
        st.markdown(f"Uploaded PDF: {uploaded_file.name}")
    save_message_to_db(st.session_state.current_convo_id, "user", f"Uploaded PDF: {uploaded_file.name}")
    
    # Run workflow
    with st.spinner("Parsing PDF document through LangGraph..."):
        try:
            initial_state = {
                "input_url": temp_path,
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
            }
            
            # Process through workflow
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {result['error']}"})
                save_message_to_db(st.session_state.current_convo_id, "assistant", f"Error: {result['error']}")
            else:
                st.session_state.current_state = result
                st.success("✅ PDF parsed successfully! Generating summary...")
                
                # Stream the summary
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in chat_node_stream(result):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
                
                st.balloons()
                st.rerun()
                
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Handle follow-up chat input (with streaming)
if prompt := st.chat_input("Ask a follow-up question about the study..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    save_message_to_db(st.session_state.current_convo_id, "user", prompt)
    
    # Generate response with streaming
    with st.chat_message("assistant"):
        if st.session_state.current_state:
            # Update state with new query
            chat_state = st.session_state.current_state.copy()
            chat_state["chat_query"] = prompt
            
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Stream response
                for chunk in chat_node_stream(chat_state):
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
                # Save to session and database
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        else:
            no_data_msg = "Please process a document first before asking questions."
            st.warning(no_data_msg)
            st.session_state.messages.append({"role": "assistant", "content": no_data_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", no_data_msg)

# Footer
st.divider()
st.caption("🔬 Clinical Trial Analysis System | LangGraph Workflow | Enhanced Parser | Powered by OpenAI GPT-4")
