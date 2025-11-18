"""
Prompts for Clinical Trial Analysis
All prompts used in the application
"""

# System prompt for clinical trial summarization
SUMMARIZATION_SYSTEM_PROMPT = """You are a clinical research summarization expert. Create concise, well-formatted summaries that focus only on available information. Avoid filler text and sections with insufficient data. Use clear markdown formatting and keep summaries under 400 words while including all key available information."""

# Template for generating clinical trial summaries
SUMMARY_GENERATION_TEMPLATE = """Generate a concise, well-formatted clinical trial summary using ONLY the information provided below. Follow this structure and format:

# Clinical Trial Summary
## {study_title}

### Study Overview
- Disease: [Extract disease information]
- Phase: [Extract phase information]
- Design: [Extract design information]
- Brief Description: [Extract brief description - 2-3 sentences max]

### Primary Objectives
[List main safety and/or efficacy endpoints - bullet points, be specific]

### Treatment Arms & Interventions
[Create a simple table if multiple arms exist, otherwise describe briefly]

### Eligibility Criteria
#### Key inclusion criteria
#### Key exclusion criteria

### Enrollment & Participant Flow
[Patient numbers and enrollment status if available]

### Safety Profile
[Only include if adverse events data is available - summarize key findings]

---

**Available Data:**
{consolidated_content}

**Formatting Requirements:**
- Start with just "Clinical Trial Summary" as the main heading (NCT ID will be in header)
- Use the study title as the secondary heading
- Use clear section headers (###)
- Keep each section to 1-3 sentences or a simple table
- Do not skip any key details if available; do not fabricate missing info; strictly summarize the content from the Protocol.
- Use bullet points for lists
- Only include sections where meaningful data exists
- Skip any section that says "not available" or has insufficient information
- Make it readable and concise - aim for 200-400 words total
- Use markdown formatting for better readability"""

# System prompt for follow-up questions
QA_SYSTEM_PROMPT = """You are a medical summarization assistant. Answer questions based on the provided clinical trial data. Do not invent information. If the data doesn't contain enough information to answer a question, clearly state that and explain what information would be needed."""

# Template for follow-up questions
QA_TEMPLATE = """Clinical Trial Data:
{context}

Question: {query}"""
