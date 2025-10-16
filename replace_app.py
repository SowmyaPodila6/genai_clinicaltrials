import os
import time

# Delete old app.py
if os.path.exists('app.py'):
    os.remove('app.py')
    print("Deleted old app.py")
    time.sleep(1)

# Create new app.py with ChatGPT-style interface
new_app_content = '''"""
Clinical Trial Analysis Chatbot - ChatGPT-like Interface
LangGraph Workflow + Streamlit
"""

import streamlit as st
import json
import uuid
import sqlite3
import os
from langgraph_workflow import build_workflow, chat_node_stream
from dotenv import load_dotenv
import re
from fpdf import FPDF

load_dotenv()

# Database functions
DB_FILE = "chat_history.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(\\'''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    \\''')
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
    st.session_state.current_state = None
    st.session_state.uploaded_file = None
    st.rerun()

# Page configuration
st.set_page_config(
    page_title="Clinical Trial Analysis",
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

if "current_state" not in st.session_state:
    st.session_state.current_state = None

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# Title
st.title("🔬 Clinical Trial Analysis Assistant")

# Sidebar
with st.sidebar:
    st.header("💬 Chat History")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        new_chat_click()
    
    st.divider()
    
    conversations = get_all_conversations()
    for convo_id in conversations[:10]:
        if st.button(f"💬 {convo_id[:8]}...", key=f"conv_{convo_id}", use_container_width=True):
            st.session_state.messages = load_messages_from_db(convo_id)
            st.session_state.current_convo_id = convo_id
            st.rerun()
    
    # Show metrics if state exists
    if st.session_state.current_state:
        st.divider()
        st.header("📊 Extraction Metrics")
        
        state = st.session_state.current_state
        
        col1, col2 = st.columns(2)
        with col1:
            confidence = state.get("confidence_score", 0)
            st.metric("Confidence", f"{confidence:.1%}")
        with col2:
            completeness = state.get("completeness_score", 0)
            st.metric("Completeness", f"{completeness:.1%}")
        
        missing = state.get("missing_fields", [])
        if missing:
            with st.expander(f"⚠️ Missing {len(missing)} fields"):
                for field in missing:
                    st.write(f"• {field.replace('_', ' ').title()}")
        
        # Download buttons
        st.divider()
        st.subheader("📥 Downloads")
        
        if state.get("parsed_json"):
            json_str = json.dumps(state["parsed_json"], indent=2)
            st.download_button(
                "📄 Download JSON",
                json_str,
                file_name=f"trial_{state.get('nct_id', 'data')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        if state.get("chat_response"):
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=10)
                
                summary_text = state.get("chat_response", "")
                for line in summary_text.split('\\n'):
                    try:
                        clean_line = line.encode('latin-1', 'ignore').decode('latin-1')
                        pdf.multi_cell(0, 5, clean_line)
                    except:
                        pass
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1', 'ignore')
                
                st.download_button(
                    "📑 Download PDF Summary",
                    pdf_bytes,
                    file_name=f"summary_{state.get('nct_id', 'report')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except:
                pass

# Welcome message
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("""
### 👋 Welcome to Clinical Trial Analysis Assistant!

I can help you analyze clinical trial documents. Here's how:

**📋 Paste a ClinicalTrials.gov URL**
- Example: `https://clinicaltrials.gov/study/NCT03991871`

**📎 Upload a PDF**
- Click the 📎 button below

**💬 Ask questions:**
- "Summarize this trial"
- "What are the eligibility criteria?"
- "Describe the treatment arms"

Let's get started! 👇
        """)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input with file upload
col1, col2 = st.columns([0.1, 0.9])

with col1:
    uploaded_file = st.file_uploader(
        "📎",
        type=["pdf"],
        label_visibility="collapsed",
        key="file_uploader"
    )

with col2:
    prompt = st.chat_input("Paste a ClinicalTrials.gov URL or ask a question...")

# Handle file upload
if uploaded_file is not None and uploaded_file != st.session_state.uploaded_file:
    st.session_state.uploaded_file = uploaded_file
    
    temp_path = f"temp_{uploaded_file.name}"
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.getvalue())
    
    st.session_state.messages.append({"role": "user", "content": f"📄 Uploaded: {uploaded_file.name}"})
    save_message_to_db(st.session_state.current_convo_id, "user", f"📄 Uploaded: {uploaded_file.name}")
    
    with st.spinner("📊 Extracting data from PDF..."):
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
            
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                error_msg = f"❌ Error: {result['error']}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
            else:
                st.session_state.current_state = result
                
                metrics_msg = f"""
📊 **Extraction Metrics:**
- Confidence: {result['confidence_score']:.1%}
- Completeness: {result['completeness_score']:.1%}
- Missing Fields: {len(result['missing_fields'])}

---
"""
                
                full_response = metrics_msg
                for chunk in chat_node_stream(result):
                    full_response += chunk
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
        
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    st.rerun()

# Handle chat input
if prompt:
    nct_match = re.search(r"NCT\\d{8}", prompt) or re.search(r"clinicaltrials\\.gov", prompt.lower())
    
    if nct_match and "http" in prompt.lower():
        st.session_state.messages.append({"role": "user", "content": f"🔗 {prompt}"})
        save_message_to_db(st.session_state.current_convo_id, "user", f"🔗 {prompt}")
        
        with st.spinner("🔍 Fetching from ClinicalTrials.gov..."):
            try:
                initial_state = {
                    "input_url": prompt,
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
                
                result = st.session_state.workflow_app.invoke(initial_state)
                
                if result.get("error"):
                    error_msg = f"❌ Error: {result['error']}"
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
                else:
                    st.session_state.current_state = result
                    
                    metrics_msg = f"""
📊 **Extraction Metrics:**
- **NCT ID:** {result.get('nct_id', 'N/A')}
- **Confidence:** {result['confidence_score']:.1%}
- **Completeness:** {result['completeness_score']:.1%}
- **Missing Fields:** {len(result['missing_fields'])}

---

"""
                    
                    full_response = metrics_msg
                    for chunk in chat_node_stream(result):
                        full_response += chunk
                    
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
            
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        
        st.rerun()
    
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message_to_db(st.session_state.current_convo_id, "user", prompt)
        
        if st.session_state.current_state:
            chat_state = st.session_state.current_state.copy()
            chat_state["chat_query"] = prompt
            
            try:
                full_response = ""
                for chunk in chat_node_stream(chat_state):
                    full_response += chunk
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
            
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        else:
            no_doc_msg = "⚠️ Please upload a PDF or paste a ClinicalTrials.gov URL first."
            st.session_state.messages.append({"role": "assistant", "content": no_doc_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", no_doc_msg)
        
        st.rerun()

# Footer
st.divider()
st.caption("🔬 Powered by LangGraph + GPT-4 | Enhanced Clinical Trial Parser")
'''

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_app_content)

print("✅ Created new app.py with ChatGPT-style interface")
print("File size:", os.path.getsize('app.py'), "bytes")
