"""
Complete Streamlit App with LangGraph Workflow
Following app_v1.py structure with all features:
- PDF generation
- JSON downloads
- Streaming chatbot
- Chat history database
- Download options
"""

import streamlit as st
import json
import uuid
import sqlite3
from langgraph_workflow import build_workflow, chat_node_stream
from dotenv import load_dotenv
import re
import os
from fpdf import FPDF
import unicodedata

load_dotenv()

# Database functions (exact copy from app_v1)
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

# PDF generation function (exact copy from app_v1)
def create_summary_pdf(summary_text, nct_id):
    try:
        def clean_text_for_pdf(text):
            if not text:
                return ""
            try:
                cleaned = text.encode('ascii', 'ignore').decode('ascii')
                return cleaned
            except:
                normalized = unicodedata.normalize('NFKD', text)
                ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
                return ascii_text
        
        class CustomPDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 14)
                self.set_text_color(0, 51, 102)
                self.cell(0, 10, f'Clinical Trial Summary: {nct_id}', 0, 1, 'C')
                self.ln(3)
            
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
        pdf = CustomPDF()
        pdf.add_page()
        pdf.set_margins(15, 25, 15)
        
        # Add URL link
        pdf.set_font("Arial", 'U', 10)
        url_text = f"https://clinicaltrials.gov/study/{nct_id}"
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 8, url_text, 0, 1, 'C', link=url_text)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)

        clean_summary = clean_text_for_pdf(summary_text)
        lines = clean_summary.split('\n')
        
        def write_wrapped_text(pdf, text, font_size=10, font_style='', indent=0):
            pdf.set_font("Arial", font_style, font_size)
            page_width = pdf.w - 2 * pdf.l_margin - indent
            words = text.split(' ')
            current_line = ""
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                if pdf.get_string_width(test_line) < page_width:
                    current_line = test_line
                else:
                    if current_line:
                        if indent > 0:
                            pdf.cell(indent, 6, '', 0, 0)
                        pdf.cell(0, 6, current_line, 0, 1, 'L')
                    current_line = word
            
            if current_line:
                if indent > 0:
                    pdf.cell(indent, 6, '', 0, 0)
                pdf.cell(0, 6, current_line, 0, 1, 'L')
        
        for line in lines:
            try:
                line = line.strip()
                if not line:
                    pdf.ln(3)
                    continue
                
                if line.startswith('# '):
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 16)
                    pdf.set_text_color(0, 51, 102)
                    header_text = clean_text_for_pdf(line.replace('# ', ''))
                    write_wrapped_text(pdf, header_text, 16, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(3)
                
                elif line.startswith('## '):
                    pdf.ln(6)
                    pdf.set_font("Arial", 'B', 14)
                    pdf.set_text_color(51, 102, 153)
                    header_text = clean_text_for_pdf(line.replace('## ', ''))
                    write_wrapped_text(pdf, header_text, 14, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(2)
                
                elif line.startswith('### '):
                    pdf.ln(4)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(102, 153, 204)
                    header_text = clean_text_for_pdf(line.replace('### ', ''))
                    write_wrapped_text(pdf, header_text, 12, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(2)
                
                elif '**' in line:
                    bold_text = clean_text_for_pdf(line.replace('**', ''))
                    write_wrapped_text(pdf, bold_text, 11, 'B')
                
                elif line.startswith('• ') or line.startswith('- '):
                    bullet_text = clean_text_for_pdf(line)
                    write_wrapped_text(pdf, bullet_text, 10, '', 8)
                
                elif '|' in line and line.count('|') >= 2:
                    pdf.set_font("Arial", '', 9)
                    table_text = clean_text_for_pdf(line)
                    if len(table_text) > 120:
                        table_text = table_text[:117] + "..."
                    pdf.cell(0, 5, table_text, 0, 1, 'L')
                
                else:
                    regular_text = clean_text_for_pdf(line)
                    if regular_text.strip():
                        write_wrapped_text(pdf, regular_text, 10, '')
                
            except Exception as e:
                continue

        return pdf.output(dest='S').encode('latin1', 'ignore')
        
    except Exception as e:
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, "PDF Generation Error", ln=True)
            pdf.cell(0, 10, f"NCT ID: {nct_id}", ln=True)
            pdf.cell(0, 10, "Please download the summary as text instead.", ln=True)
            return pdf.output(dest='S').encode('latin1', 'ignore')
        except:
            return b"PDF generation failed due to encoding issues."

def new_chat_click():
    st.session_state.messages = []
    st.session_state.current_convo_id = str(uuid.uuid4())
    st.session_state.url_key = str(uuid.uuid4())
    st.session_state.current_state = None
    st.rerun()

# Page configuration
st.set_page_config(
    page_title="Clinical Trial Analysis - LangGraph Powered",
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
st.markdown("**LangGraph Workflow Edition** | Enter a ClinicalTrials.gov URL or upload a PDF document to get a section-by-section summary")

# Sidebar
st.sidebar.header("Past Chats")
conversations = get_all_conversations()
for convo_id in conversations:
    if st.sidebar.button(convo_id, key=f"conv_{convo_id}"):
        st.session_state.messages = load_messages_from_db(convo_id)
        st.session_state.current_convo_id = convo_id
        # Restore summary data
        for msg in st.session_state.messages:
            if msg["role"] == "assistant" and "Clinical Trial Summary" in msg["content"]:
                nct_match = re.search(r"NCT\d{8}", msg["content"])
                if nct_match:
                    st.session_state.current_summary = msg["content"]
                    st.session_state.current_nct_id = nct_match.group(0)
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
    with st.spinner("Fetching protocol details and generating summary..."):
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
            
            # Process through workflow
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {result['error']}"})
                save_message_to_db(st.session_state.current_convo_id, "assistant", f"Error: {result['error']}")
            else:
                st.session_state.current_state = result
                st.success("✅ Protocol details fetched successfully! Generating summary...")
                
                # Stream the summary
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in chat_node_stream(result):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                
                # Save to database and session
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_message_to_db(st.session_state.current_convo_id, "assistant", full_response)
                
                # Store for download options (same as app_v1)
                st.session_state.current_summary = full_response
                st.session_state.current_nct_id = result.get("nct_id", nct_number)
                st.session_state.raw_json_data = result.get("raw_data", {})
                st.session_state.processed_data = result.get("data_to_summarize", {})
                
                # Show download options
                st.markdown("---")
                st.markdown("### 📥 Download Options")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    try:
                        pdf_data = create_summary_pdf(full_response, result.get("nct_id", nct_number))
                        st.download_button(
                            label="📄 Summary PDF",
                            data=pdf_data,
                            file_name=f"clinical_trial_summary_{result.get('nct_id', nct_number)}.pdf",
                            mime="application/pdf",
                            key="main_pdf_download"
                        )
                    except Exception as e:
                        st.error("PDF generation error")
                
                with col2:
                    text_summary = f"Clinical Trial Summary: {result.get('nct_id', nct_number)}\n"
                    text_summary += f"URL: https://clinicaltrials.gov/study/{result.get('nct_id', nct_number)}\n\n"
                    text_summary += full_response
                    
                    st.download_button(
                        label="📝 Summary Text",
                        data=text_summary.encode('utf-8'),
                        file_name=f"clinical_trial_summary_{result.get('nct_id', nct_number)}.txt",
                        mime="text/plain",
                        key="main_text_download"
                    )
                
                with col3:
                    raw_json_str = json.dumps(result.get("raw_data", {}), indent=2, ensure_ascii=False)
                    st.download_button(
                        label="🗂️ Raw JSON",
                        data=raw_json_str.encode('utf-8'),
                        file_name=f"raw_study_data_{result.get('nct_id', nct_number)}.json",
                        mime="application/json",
                        key="main_raw_json_download"
                    )
                
                with col4:
                    processed_json_str = json.dumps(result.get("data_to_summarize", {}), indent=2, ensure_ascii=False)
                    st.download_button(
                        label="⚙️ Processed Data",
                        data=processed_json_str.encode('utf-8'),
                        file_name=f"processed_data_{result.get('nct_id', nct_number)}.json",
                        mime="application/json",
                        key="main_processed_data_download"
                    )
                
                with col5:
                    comprehensive_data = {
                        "metadata": {
                            "nct_id": result.get("nct_id", nct_number),
                            "confidence_score": result.get("confidence_score", 0),
                            "completeness_score": result.get("completeness_score", 0),
                            "missing_fields": result.get("missing_fields", [])
                        },
                        "raw_data": result.get("raw_data", {}),
                        "processed_data": result.get("data_to_summarize", {}),
                        "summary": full_response
                    }
                    comprehensive_json = json.dumps(comprehensive_data, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📦 Complete Package",
                        data=comprehensive_json.encode('utf-8'),
                        file_name=f"complete_study_package_{result.get('nct_id', nct_number)}.json",
                        mime="application/json",
                        key="main_comprehensive_download"
                    )
                
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
    with st.spinner("Parsing PDF document through LangGraph (Enhanced Parser)..."):
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
                
                # Show extraction metrics
                conf_msg = f"**Extraction Metrics:**\n- Confidence: {result.get('confidence_score', 0):.1%}\n- Completeness: {result.get('completeness_score', 0):.1%}\n- Missing fields: {len(result.get('missing_fields', []))}"
                st.info(conf_msg)
                
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
                
                # Store for download options
                st.session_state.current_summary = full_response
                st.session_state.current_nct_id = result.get("nct_id", "PDF")
                st.session_state.parsed_sections = result.get("parsed_json", {})
                
                st.balloons()
                st.rerun()
                
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            save_message_to_db(st.session_state.current_convo_id, "assistant", error_msg)
        finally:
            # Clean up temp file
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

# Show persistent download options if summary exists
if hasattr(st.session_state, 'current_summary') and st.session_state.current_summary and not url_input:
    st.markdown("---")
    st.markdown("### 📥 Download Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            pdf_data = create_summary_pdf(
                st.session_state.current_summary, 
                st.session_state.current_nct_id
            )
            st.download_button(
                label="📄 Summary PDF",
                data=pdf_data,
                file_name=f"clinical_trial_summary_{st.session_state.current_nct_id}.pdf",
                mime="application/pdf",
                key="persistent_pdf_download"
            )
        except Exception as e:
            st.error("PDF generation error")
    
    with col2:
        text_summary = f"Clinical Trial Summary: {st.session_state.current_nct_id}\n\n"
        text_summary += st.session_state.current_summary
        
        st.download_button(
            label="📝 Summary Text",
            data=text_summary.encode('utf-8'),
            file_name=f"clinical_trial_summary_{st.session_state.current_nct_id}.txt",
            mime="text/plain",
            key="persistent_text_download"
        )
    
    with col3:
        if hasattr(st.session_state, 'parsed_sections'):
            parsed_json = json.dumps(st.session_state.parsed_sections, indent=2)
            st.download_button(
                label="📄 Parsed JSON",
                data=parsed_json,
                file_name=f"parsed_data_{st.session_state.current_nct_id}.json",
                mime="application/json",
                key="persistent_json_download"
            )

# Footer
st.divider()
st.caption("🔬 Clinical Trial Analysis System | **LangGraph Workflow** | Enhanced Parser | Powered by OpenAI GPT-4o")
