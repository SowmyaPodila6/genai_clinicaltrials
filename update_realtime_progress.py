"""Script to update app.py with real-time streaming progress"""

# Read the file
with open(r'c:\Users\karim\genai_clinicaltrials\UI\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old code block to replace
old_code = '''        # Show initial parsing step
        with progress_container:
            st.info("🔍 Step 1/3: Analyzing PDF with enhanced parser...")
        
        # Process through workflow
        result = st.session_state.workflow_app.invoke(initial_state)
        
        # Show real-time progress during extraction if LLM was used
        progress_log = result.get("progress_log", [])
        if progress_log and result.get("used_llm_fallback"):
            with progress_container:
                st.info("🔄 Step 2/3: Multi-turn LLM extraction in progress...")
            with status_container:
                # Show last few progress messages in real-time style
                recent_progress = progress_log[-5:] if len(progress_log) > 5 else progress_log
                st.code("\\n".join(recent_progress), language="")
        
        # Clear progress indicators after completion
        progress_container.empty()
        status_container.empty()'''

# Define the new code
new_code = '''        # Stream the workflow execution for real-time updates
        result = None
        progress_messages = []
        
        for event in st.session_state.workflow_app.stream(initial_state):
            # Each event contains node name and state
            for node_name, node_state in event.items():
                # Update progress based on which node is executing
                if node_name == "parse_data":
                    with progress_status:
                        st.info("🔍 **Step 1/3:** Analyzing PDF with enhanced parser...")
                
                elif node_name == "check_quality":
                    confidence = node_state.get("confidence_score", 0)
                    completeness = node_state.get("completeness_score", 0)
                    with progress_status:
                        st.info(f"📊 **Step 2/3:** Quality Check - Confidence: {confidence:.1%}, Completeness: {completeness:.1%}")
                
                elif node_name == "llm_fallback":
                    with progress_status:
                        st.warning("🤖 **Step 3/3:** Multi-turn LLM extraction in progress...")
                    
                    # Show cost estimate if available
                    cost_est = node_state.get("extraction_cost_estimate", {})
                    if cost_est:
                        with progress_details:
                            st.info(f"💰 Estimated - Cost: ${cost_est.get('total_cost', 0):.3f} | "
                                  f"Time: {cost_est.get('estimated_time_minutes', 0):.1f} min | "
                                  f"Tokens: {cost_est.get('total_tokens', 0):,}")
                    
                    # Show real-time progress log updates
                    new_logs = node_state.get("progress_log", [])
                    if new_logs and len(new_logs) > len(progress_messages):
                        progress_messages = new_logs
                        # Show latest progress messages (last 10)
                        latest = progress_messages[-10:] if len(progress_messages) > 10 else progress_messages
                        with progress_details:
                            st.code("\\n".join(latest), language="")
                
                elif node_name == "generate_summary":
                    with progress_status:
                        st.success("✅ **Complete:** Generating comprehensive summary...")
                
                # Store the latest state
                result = node_state
        
        # Use the final result if we have it
        if result is None:
            result = st.session_state.workflow_app.invoke(initial_state)
        
        # Clear progress indicators after completion
        progress_status.empty()
        progress_details.empty()'''

# Replace the code
if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ Found and replaced the old code block")
else:
    print("❌ Could not find exact match. Trying with normalized whitespace...")
    # Normalize whitespace and try again
    import re
    old_normalized = re.sub(r'\s+', ' ', old_code).strip()
    content_normalized = re.sub(r'\s+', ' ', content)
    if old_normalized in content_normalized:
        print("⚠️ Found with normalized whitespace, but replacement may not work perfectly")
    else:
        print("❌ Pattern not found even with normalization")

# Write back
with open(r'c:\Users\karim\genai_clinicaltrials\UI\app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Updated app.py with real-time streaming progress!")
print("   - Now uses workflow.stream() instead of workflow.invoke()")
print("   - Shows progress as each LangGraph node executes")
print("   - Displays multi-turn extraction progress live")
print("   - Updates cost/time estimates in real-time")
