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

def create_metrics_message(state):
    """Create a formatted metrics message from workflow state"""
    confidence = state.get("confidence_score", 0)
    completeness = state.get("completeness_score", 0)
    missing_fields = state.get("missing_fields", [])
    nct_id = state.get("nct_id", "Unknown")
    input_type = state.get("input_type", "unknown")
    parsed_json = state.get("parsed_json", {})
    
    # Count filled fields based on meaningful content
    total_fields = 9
    filled_fields = total_fields - len(missing_fields)
    
    # Determine if LLM fallback was used
    used_llm_fallback = state.get("used_llm_fallback", False)
    
    # List all fields for reference
    all_fields = [
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
    
    message = f"""
### 📊 Extraction Metrics

**Study ID:** {nct_id}  
**Input Type:** {input_type.upper()}  

**Quality Scores:**
- **Confidence Score:** {confidence:.1%} {'✅' if confidence >= 0.7 else '⚠️' if confidence >= 0.5 else '❌'}
- **Completeness Score:** {completeness:.1%} {'✅' if completeness >= 0.8 else '⚠️' if completeness >= 0.6 else '❌'}

**Field Extraction:**
- **Extracted:** {filled_fields}/{total_fields} fields

**Character Count by Section:**
"""
    
    # Add character count for each field
    for field in all_fields:
        field_name = field.replace('_', ' ').title()
        content = parsed_json.get(field)
        
        if content and isinstance(content, str) and content.strip():
            char_count = len(content.strip())
            status = '✅' if char_count > 30 else '⚠️'
            message += f"- **{field_name}:** {char_count:,} chars {status}\n"
        else:
            message += f"- **{field_name}:** 0 chars ❌\n"
    
    message += "\n"
    
    if missing_fields:
        message += f"**Missing/Insufficient Fields:** {len(missing_fields)}\n"
    else:
        message += "**All fields extracted successfully!** ✅\n"
    
    if used_llm_fallback:
        message += "\n**🤖 LLM Enhancement:** Quality scores were below threshold. Advanced AI extraction was used to improve completeness.\n"
    
    return message

def create_summary_pdf(summary_text, nct_id):
    """Create PDF from summary text"""
    try:
        from fpdf import FPDF
        import unicodedata
        
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
                    pdf.multi_cell(0, 8, line.replace('# ', ''))
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(3)
                elif line.startswith('## '):
                    pdf.ln(6)
                    pdf.set_font("Arial", 'B', 14)
                    pdf.multi_cell(0, 7, line.replace('## ', ''))
                    pdf.ln(2)
                elif line.startswith('### '):
                    pdf.ln(4)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.multi_cell(0, 6, line.replace('### ', ''))
                    pdf.ln(2)
                elif '**' in line:
                    pdf.set_font("Arial", 'B', 11)
                    pdf.multi_cell(0, 6, line.replace('**', ''))
                elif line.startswith('- ') or line.startswith('• '):
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(8, 6, '', 0, 0)
                    pdf.multi_cell(0, 6, line)
                else:
                    pdf.set_font("Arial", '', 10)
                    pdf.multi_cell(0, 6, line)
            except:
                continue

        return pdf.output(dest='S').encode('latin1', 'ignore')
        
    except Exception as e:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "PDF Generation Error", ln=True)
        pdf.cell(0, 10, f"NCT ID: {nct_id}", ln=True)
        return pdf.output(dest='S').encode('latin1', 'ignore')

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
st.title("Gen AI-Powered Clinical Protocol Summarizer")
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
    
    # Download buttons section
    st.sidebar.divider()
    st.sidebar.subheader("📥 Downloads")
    
    # JSON Download
    if state.get("parsed_json"):
        json_str = json.dumps(state["parsed_json"], indent=2)
        st.sidebar.download_button(
            "📄 Download JSON Data",
            json_str,
            file_name=f"clinical_trial_{state.get('nct_id', 'data')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # PDF Summary Download
    if state.get("chat_response"):
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            
            summary_text = state.get("chat_response", "")
            for line in summary_text.split('\n'):
                try:
                    clean_line = line.encode('latin-1', 'ignore').decode('latin-1')
                    pdf.multi_cell(0, 5, clean_line)
                except:
                    pass
            
            pdf_bytes = pdf.output(dest='S').encode('latin-1', 'ignore')
            
            st.sidebar.download_button(
                "📑 Download PDF Summary",
                pdf_bytes,
                file_name=f"summary_{state.get('nct_id', 'report')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.sidebar.error(f"PDF generation error: {str(e)[:50]}")
    
    # Raw data download (optional)
    if state.get("raw_data"):
        raw_json_str = json.dumps(state["raw_data"], indent=2)
        st.sidebar.download_button(
            "�️ Download Raw Data",
            raw_json_str,
            file_name=f"raw_data_{state.get('nct_id', 'data')}.json",
            mime="application/json",
            use_container_width=True
        )

# Welcome message if no messages
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("""
👋 **Welcome to the Clinical Trial Analysis Assistant!**

I can help you analyze clinical trial documents. You can:

- 📋 **Paste a ClinicalTrials.gov URL** (e.g., `https://clinicaltrials.gov/study/NCT03991871`)
- 📄 **Upload a PDF document** using the 📎 button below
- 💬 **Ask questions** about the extracted data

Just paste a URL or upload a file to get started!
        """)

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input widgets - URL/File upload (only show on initial state)
url_input = None
nct_match = None
uploaded_file = None

if not st.session_state.messages:
    # URL input
    url_input = st.text_input(
        "🔗 Enter ClinicalTrials.gov URL:",
        placeholder="https://clinicaltrials.gov/study/NCT03991871",
        key=st.session_state.get("url_key", "url_input")
    )
    
    # File uploader
    uploaded_file = st.file_uploader(
        "📎 Or upload a PDF document:",
        type=["pdf"],
        key="pdf_uploader"
    )
    
    # Check for NCT number in URL
    if url_input:
        nct_match = re.search(r'NCT\d{8}', url_input)

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
                "error": "",
                "used_llm_fallback": False
            }
            
            # Process through workflow (non-streaming for initial extraction)
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {result['error']}"})
                save_message_to_db(st.session_state.current_convo_id, "assistant", f"Error: {result['error']}")
            else:
                st.session_state.current_state = result
                st.success("✅ Data extracted successfully!")
                
                # Show metrics as a chat message
                metrics_msg = create_metrics_message(result)
                with st.chat_message("assistant"):
                    st.markdown(metrics_msg)
                st.session_state.messages.append({"role": "assistant", "content": metrics_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", metrics_msg)
                
                # Show status message about what's happening next
                status_msg = "📝 Generating comprehensive summary..."
                with st.chat_message("assistant"):
                    st.markdown(status_msg)
                st.session_state.messages.append({"role": "assistant", "content": status_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", status_msg)
                
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
                
                # Show download options
                st.markdown("---")
                st.markdown("### 📥 Download Options")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # PDF Download
                    try:
                        pdf_data = create_summary_pdf(full_response, result.get('nct_id', 'study'))
                        st.download_button(
                            label="📄 Summary PDF",
                            data=pdf_data,
                            file_name=f"clinical_trial_summary_{result.get('nct_id', 'study')}.pdf",
                            mime="application/pdf",
                            key="url_pdf_download"
                        )
                    except Exception as e:
                        st.error("PDF gen error")
                
                with col2:
                    # Text Download
                    text_summary = f"Clinical Trial Summary: {result.get('nct_id', 'Unknown')}\n\n{full_response}"
                    st.download_button(
                        label="📝 Summary Text",
                        data=text_summary.encode('utf-8'),
                        file_name=f"summary_{result.get('nct_id', 'study')}.txt",
                        mime="text/plain",
                            key="url_text_download"
                    )
                
                with col3:
                    # Parsed JSON - always available after extraction
                    parsed_json = result.get("parsed_json", {})
                    # Filter out None values for cleaner JSON
                    filtered_json = {k: v for k, v in parsed_json.items() if v is not None} if parsed_json else {}
                    
                    if filtered_json:
                        json_str = json.dumps(filtered_json, indent=2)
                        st.download_button(
                            label="📄 Parsed JSON",
                            data=json_str,
                            file_name=f"parsed_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="url_parsed_json"
                        )
                    else:
                        # Show empty JSON if no data extracted
                        st.download_button(
                            label="📄 Parsed JSON",
                            data=json.dumps(parsed_json, indent=2),
                            file_name=f"parsed_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="url_parsed_json",
                            help="No data extracted"
                        )
                
                with col4:
                    # Raw data - always available for URL mode
                    raw_data = result.get("raw_data", {})
                    
                    if raw_data:
                        raw_json_str = json.dumps(raw_data, indent=2)
                        st.download_button(
                            label="🗂️ Raw Data",
                            data=raw_json_str,
                            file_name=f"raw_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="url_raw_data"
                        )
                    else:
                        # Show empty JSON if no raw data
                        st.download_button(
                            label="🗂️ Raw Data",
                            data="{}",
                            file_name=f"raw_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="url_raw_data",
                            help="No raw data available"
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
                "error": "",
                "used_llm_fallback": False
            }
            
            # Process through workflow
            result = st.session_state.workflow_app.invoke(initial_state)
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {result['error']}"})
                save_message_to_db(st.session_state.current_convo_id, "assistant", f"Error: {result['error']}")
            else:
                st.session_state.current_state = result
                st.success("✅ PDF parsed successfully!")
                
                # Show metrics as a chat message
                metrics_msg = create_metrics_message(result)
                with st.chat_message("assistant"):
                    st.markdown(metrics_msg)
                st.session_state.messages.append({"role": "assistant", "content": metrics_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", metrics_msg)
                
                # Show status message about what's happening next
                status_msg = "📝 Generating comprehensive summary..."
                with st.chat_message("assistant"):
                    st.markdown(status_msg)
                st.session_state.messages.append({"role": "assistant", "content": status_msg})
                save_message_to_db(st.session_state.current_convo_id, "assistant", status_msg)
                
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
                
                # Show download options
                st.markdown("---")
                st.markdown("### 📥 Download Options")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    # PDF Download
                    try:
                        pdf_data = create_summary_pdf(full_response, result.get('nct_id', 'study'))
                        st.download_button(
                            label="📄 Summary PDF",
                            data=pdf_data,
                            file_name=f"clinical_trial_summary_{result.get('nct_id', 'study')}.pdf",
                            mime="application/pdf",
                            key="pdf_upload_pdf_download"
                        )
                    except Exception as e:
                        st.error("PDF gen error")
                
                with col2:
                    # Text Download
                    text_summary = f"Clinical Trial Summary: {result.get('nct_id', 'Unknown')}\n\n{full_response}"
                    st.download_button(
                        label="📝 Summary Text",
                        data=text_summary.encode('utf-8'),
                        file_name=f"summary_{result.get('nct_id', 'study')}.txt",
                        mime="text/plain",
                        key="pdf_upload_text_download"
                    )
                
                with col3:
                    # Parsed JSON - always available after extraction
                    parsed_json = result.get("parsed_json", {})
                    # Filter out None values for cleaner JSON
                    filtered_json = {k: v for k, v in parsed_json.items() if v is not None} if parsed_json else {}
                    
                    if filtered_json:
                        json_str = json.dumps(filtered_json, indent=2)
                        st.download_button(
                            label="📄 Parsed JSON",
                            data=json_str,
                            file_name=f"parsed_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="pdf_upload_parsed_json"
                        )
                    else:
                        # Show empty JSON if no data extracted
                        st.download_button(
                            label="📄 Parsed JSON",
                            data=json.dumps(parsed_json, indent=2),
                            file_name=f"parsed_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="pdf_upload_parsed_json",
                            help="No data extracted"
                        )
                
                with col4:
                    # Raw data - always available for PDF mode
                    raw_data = result.get("raw_data", {})
                    
                    if raw_data:
                        raw_json_str = json.dumps(raw_data, indent=2)
                        st.download_button(
                            label="🗂️ Raw Data",
                            data=raw_json_str,
                            file_name=f"raw_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="pdf_upload_raw_data"
                        )
                    else:
                        # Show empty JSON if no raw data
                        st.download_button(
                            label="🗂️ Raw Data",
                            data="{}",
                            file_name=f"raw_data_{result.get('nct_id', 'study')}.json",
                            mime="application/json",
                            key="pdf_upload_raw_data",
                            help="No raw data available"
                        )
                
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
