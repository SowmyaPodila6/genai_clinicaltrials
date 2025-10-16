"""
Streamlit App with LangGraph Workflow Integration
Interactive Clinical Trial Analysis Chatbot
"""

import streamlit as st
import json
from langgraph_workflow import build_workflow
from dotenv import load_dotenv

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Clinical Trial Analysis",
    page_icon="🔬",
    layout="wide"
)

# Initialize session state
if "workflow_app" not in st.session_state:
    st.session_state.workflow_app = build_workflow()

if "current_state" not in st.session_state:
    st.session_state.current_state = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Title and description
st.title("🔬 Clinical Trial Analysis Chatbot")
st.markdown("**Powered by LangGraph | AI-Driven Clinical Trial Extraction & Analysis**")

# Sidebar for configuration
with st.sidebar:
    st.header("📊 Workflow Status")
    
    if st.session_state.current_state:
        state = st.session_state.current_state
        
        st.metric("Input Type", state.get("input_type", "N/A").upper())
        
        col1, col2 = st.columns(2)
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
                delta="Complete" if completeness > 0.8 else "Incomplete"
            )
        
        missing = state.get("missing_fields", [])
        if missing:
            st.warning(f"**Missing Fields ({len(missing)}):**")
            for field in missing:
                st.write(f"- {field.replace('_', ' ').title()}")
        else:
            st.success("✅ All fields extracted!")
        
        # Download options
        st.divider()
        st.subheader("📥 Downloads")
        
        if state.get("parsed_json"):
            json_str = json.dumps(state["parsed_json"], indent=2)
            st.download_button(
                "📄 Download JSON",
                json_str,
                file_name="clinical_trial_data.json",
                mime="application/json"
            )
    else:
        st.info("Submit a document to see metrics")
    
    st.divider()
    
    # Reset button
    if st.button("🔄 New Analysis", use_container_width=True):
        st.session_state.current_state = None
        st.session_state.chat_history = []
        st.rerun()


# Main content
tab1, tab2, tab3 = st.tabs(["📤 Input", "💬 Chat", "📊 Data View"])

with tab1:
    st.header("Document Input")
    
    input_method = st.radio(
        "Choose input method:",
        ["ClinicalTrials.gov URL", "PDF Upload", "PDF URL"],
        horizontal=True
    )
    
    input_value = None
    
    if input_method == "ClinicalTrials.gov URL":
        input_value = st.text_input(
            "Enter URL",
            placeholder="https://clinicaltrials.gov/study/NCT03991871"
        )
    
    elif input_method == "PDF Upload":
        uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
        if uploaded_file:
            # Save temporarily
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getvalue())
            input_value = temp_path
    
    elif input_method == "PDF URL":
        input_value = st.text_input(
            "Enter PDF URL",
            placeholder="https://example.com/clinical_trial.pdf"
        )
    
    if st.button("🚀 Process Document", type="primary", disabled=not input_value):
        with st.spinner("Processing document through LangGraph workflow..."):
            try:
                # Initialize state
                initial_state = {
                    "input_url": input_value,
                    "input_type": "unknown",
                    "raw_data": {},
                    "parsed_json": {},
                    "confidence_score": 0.0,
                    "completeness_score": 0.0,
                    "missing_fields": [],
                    "chat_query": "",
                    "chat_response": "",
                    "error": ""
                }
                
                # Run workflow
                result = st.session_state.workflow_app.invoke(initial_state)
                
                # Store result
                st.session_state.current_state = result
                
                if result.get("error"):
                    st.error(f"Error: {result['error']}")
                else:
                    st.success("✅ Document processed successfully!")
                    st.balloons()
                    
                    # Auto-generate summary
                    summary_state = result.copy()
                    summary_state["chat_query"] = "Provide a concise summary"
                    summary_result = st.session_state.workflow_app.invoke(summary_state)
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": summary_result["chat_response"]
                    })
                
            except Exception as e:
                st.error(f"Processing error: {str(e)}")

with tab2:
    st.header("Interactive Chat")
    
    if not st.session_state.current_state:
        st.info("👈 Process a document first to start chatting")
    else:
        # Display chat history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask a question about the clinical trial..."):
            # Add user message
            st.session_state.chat_history.append({
                "role": "user",
                "content": prompt
            })
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Update state with query
                        chat_state = st.session_state.current_state.copy()
                        chat_state["chat_query"] = prompt
                        
                        # Run chat node
                        result = st.session_state.workflow_app.invoke(chat_state)
                        
                        response = result["chat_response"]
                        st.markdown(response)
                        
                        # Add to history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response
                        })
                        
                        # Update state
                        st.session_state.current_state = result
                        
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": error_msg
                        })

with tab3:
    st.header("Extracted Data")
    
    if not st.session_state.current_state:
        st.info("👈 Process a document to view extracted data")
    else:
        state = st.session_state.current_state
        
        # Show metrics at top
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Input Type", state.get("input_type", "N/A").upper())
        with col2:
            st.metric("Confidence", f"{state.get('confidence_score', 0):.1%}")
        with col3:
            st.metric("Completeness", f"{state.get('completeness_score', 0):.1%}")
        with col4:
            missing_count = len(state.get("missing_fields", []))
            st.metric("Missing Fields", missing_count)
        
        st.divider()
        
        # Display parsed data
        parsed_json = state.get("parsed_json", {})
        
        if parsed_json:
            # Create expandable sections for each field
            fields = [
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
            
            for field in fields:
                content = parsed_json.get(field, "")
                
                # Determine status
                if not content or len(content.strip()) < 20:
                    icon = "❌"
                    status = "Missing"
                else:
                    icon = "✅"
                    status = "Extracted"
                
                with st.expander(f"{icon} {field.replace('_', ' ').title()} - {status}"):
                    if content and len(content.strip()) >= 20:
                        st.markdown(content)
                    else:
                        st.warning("No data extracted for this field")
        else:
            st.warning("No data available")

# Footer
st.divider()
st.caption("🔬 Clinical Trial Analysis System | LangGraph Workflow | Powered by OpenAI GPT-4")
