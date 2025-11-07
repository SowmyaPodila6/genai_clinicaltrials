"""Script to update app.py with real-time streaming progress using line-based replacement"""

# Read the file
with open(r'c:\Users\karim\genai_clinicaltrials\UI\app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "# Show initial parsing step"
start_line = None
for i, line in enumerate(lines):
    if "# Show initial parsing step" in line:
        start_line = i
        break

if start_line is None:
    print("❌ Could not find start marker")
    exit(1)

# Find the end line (where we clear progress indicators)
end_line = None
for i in range(start_line, min(start_line + 30, len(lines))):
    if "if result.get(\"error\"):" in lines[i]:
        end_line = i
        break

if end_line is None:
    print("❌ Could not find end marker")
    exit(1)

print(f"Found code block from line {start_line+1} to {end_line}")
print(f"Replacing {end_line - start_line} lines...")

# New code to insert
new_code_lines = [
    "        # Stream the workflow execution for real-time updates\n",
    "        result = None\n",
    "        progress_messages = []\n",
    "        \n",
    "        for event in st.session_state.workflow_app.stream(initial_state):\n",
    "            # Each event contains node name and state\n",
    "            for node_name, node_state in event.items():\n",
    "                # Update progress based on which node is executing\n",
    "                if node_name == \"parse_data\":\n",
    "                    with progress_status:\n",
    "                        st.info(\"🔍 **Step 1/3:** Analyzing PDF with enhanced parser...\")\n",
    "                \n",
    "                elif node_name == \"check_quality\":\n",
    "                    confidence = node_state.get(\"confidence_score\", 0)\n",
    "                    completeness = node_state.get(\"completeness_score\", 0)\n",
    "                    with progress_status:\n",
    "                        st.info(f\"📊 **Step 2/3:** Quality Check - Confidence: {confidence:.1%}, Completeness: {completeness:.1%}\")\n",
    "                \n",
    "                elif node_name == \"llm_fallback\":\n",
    "                    with progress_status:\n",
    "                        st.warning(\"🤖 **Step 3/3:** Multi-turn LLM extraction in progress...\")\n",
    "                    \n",
    "                    # Show cost estimate if available\n",
    "                    cost_est = node_state.get(\"extraction_cost_estimate\", {})\n",
    "                    if cost_est:\n",
    "                        with progress_details:\n",
    "                            st.info(f\"💰 Estimated - Cost: ${cost_est.get('total_cost', 0):.3f} | \"\n",
    "                                  f\"Time: {cost_est.get('estimated_time_minutes', 0):.1f} min | \"\n",
    "                                  f\"Tokens: {cost_est.get('total_tokens', 0):,}\")\n",
    "                    \n",
    "                    # Show real-time progress log updates\n",
    "                    new_logs = node_state.get(\"progress_log\", [])\n",
    "                    if new_logs and len(new_logs) > len(progress_messages):\n",
    "                        progress_messages = new_logs\n",
    "                        # Show latest progress messages (last 10)\n",
    "                        latest = progress_messages[-10:] if len(progress_messages) > 10 else progress_messages\n",
    "                        with progress_details:\n",
    "                            st.code(\"\\n\".join(latest), language=\"\")\n",
    "                \n",
    "                elif node_name == \"generate_summary\":\n",
    "                    with progress_status:\n",
    "                        st.success(\"✅ **Complete:** Generating comprehensive summary...\")\n",
    "                \n",
    "                # Store the latest state\n",
    "                result = node_state\n",
    "        \n",
    "        # Use the final result if we have it\n",
    "        if result is None:\n",
    "            result = st.session_state.workflow_app.invoke(initial_state)\n",
    "        \n",
    "        # Clear progress indicators after completion\n",
    "        progress_status.empty()\n",
    "        progress_details.empty()\n",
    "        \n",
]

# Replace the lines
new_lines = lines[:start_line] + new_code_lines + lines[end_line:]

# Write back
with open(r'c:\Users\karim\genai_clinicaltrials\UI\app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Successfully updated app.py with real-time streaming!")
print(f"   Replaced lines {start_line+1}-{end_line} with new streaming code")
print("   - Now uses workflow.stream() for real-time updates")
print("   - Shows progress as each LangGraph node executes")
print("   - Displays multi-turn extraction progress live")
