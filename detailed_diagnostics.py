"""
Detailed diagnostics to show:
1. PDF Parser output and metrics
2. LLM Fallback output and metrics
3. Side-by-side comparison
"""

import json
import os
import sys
from pathlib import Path

# Add necessary directories to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
langgraph_dir = os.path.join(current_dir, 'langgraph')
other_dir = os.path.join(current_dir, 'other')

for directory in [langgraph_dir, other_dir, current_dir]:
    if directory not in sys.path:
        sys.path.insert(0, directory)

# Now import from the correct locations
from enhanced_parser import EnhancedClinicalTrialParser
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize LLM - use gpt-4o-mini for higher rate limits
# gpt-4o-mini: 200k TPM limit (vs 30k for gpt-4o), 15x cheaper, same 128k context
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, streaming=False)

def calculate_metrics(parsed_json: dict) -> tuple[float, float, list]:
    """Calculate confidence and completeness scores based on meaningful content (using word count)"""
    required_fields = [
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
    
    filled_fields = 0
    missing_fields = []
    total_words = 0
    
    for field in required_fields:
        content = parsed_json.get(field, "")
        
        # Check for meaningful content (not just "N/A" or short placeholders)
        if (content and 
            isinstance(content, str) and
            content.strip() != "N/A" and
            content.strip() != "" and
            "not available" not in content.lower() and
            "no data" not in content.lower() and
            len(content.strip()) > 30):  # Meaningful content threshold
            filled_fields += 1
            # Count words instead of characters
            word_count = len(content.split())
            total_words += word_count
        else:
            missing_fields.append(field)
    
    # Completeness: percentage of fields with meaningful data
    completeness_score = filled_fields / len(required_fields) if required_fields else 0.0
    
    # Confidence: based on average word count per field
    if filled_fields > 0:
        avg_word_count = total_words / filled_fields
        # Scale confidence: 20 words = 20%, 100 words = 100%
        confidence_score = min(1.0, (avg_word_count - 20) / 80 + 0.2)
        confidence_score = max(0.0, confidence_score)  # Ensure non-negative
    else:
        confidence_score = 0.0
    
    return confidence_score, completeness_score, missing_fields

def analyze_pdf_step_by_step(pdf_path):
    """Analyze PDF extraction step by step"""
    
    print("=" * 100)
    print(f"DETAILED DIAGNOSTICS FOR: {pdf_path}")
    print("=" * 100)
    print()
    
    # ========================================================================
    # STEP 1: PDF PARSER EXTRACTION
    # ========================================================================
    print("┌" + "─" * 98 + "┐")
    print("│ STEP 1: PDF PARSER EXTRACTION (EnhancedClinicalTrialParser)".ljust(99) + "│")
    print("└" + "─" * 98 + "┘")
    print()
    
    parser = EnhancedClinicalTrialParser(use_ocr=False, use_nlp=False)
    
    # Parse PDF
    print("Parsing PDF...")
    clinical_data, tables = parser.parse_pdf(pdf_path, extract_tables=True)
    
    # Convert to dict
    from dataclasses import asdict
    parsed_schema = {
        "study_overview": clinical_data.study_overview,
        "brief_description": clinical_data.brief_description,
        "primary_secondary_objectives": clinical_data.primary_secondary_objectives,
        "treatment_arms_interventions": clinical_data.treatment_arms_interventions,
        "eligibility_criteria": clinical_data.eligibility_criteria,
        "enrollment_participant_flow": clinical_data.enrollment_participant_flow,
        "adverse_events_profile": clinical_data.adverse_events_profile,
        "study_locations": clinical_data.study_locations,
        "sponsor_information": clinical_data.sponsor_information
    }
    
    # Calculate metrics for parser output
    parser_confidence, parser_completeness, parser_missing = calculate_metrics(parsed_schema)
    
    print(f"✅ Parser extraction complete")
    print()
    
    # Display parser results
    print("📊 PARSER METRICS:")
    print(f"   Confidence Score: {parser_confidence:.1%}")
    print(f"   Completeness Score: {parser_completeness:.1%}")
    print(f"   Missing Fields: {parser_missing}")
    print()
    
    print("📋 PARSER EXTRACTED DATA:")
    print("-" * 100)
    
    total_parser_words = 0
    total_parser_chars = 0
    
    for field, value in parsed_schema.items():
        if value and isinstance(value, str) and value.strip():
            word_count = len(value.split())
            char_count = len(value)
            total_parser_words += word_count
            total_parser_chars += char_count
            
            # Show preview
            preview = value[:150].replace('\n', ' ').strip()
            if len(value) > 150:
                preview += "..."
            
            print(f"\n{field}:")
            print(f"   Words: {word_count:,} | Chars: {char_count:,}")
            print(f"   Preview: {preview}")
        else:
            print(f"\n{field}:")
            print(f"   ❌ EMPTY or N/A")
    
    print()
    print(f"📈 TOTAL PARSER OUTPUT: {total_parser_words:,} words, {total_parser_chars:,} characters")
    print()
    
    # Save parser JSON
    parser_json_path = f"{Path(pdf_path).stem}_parser_output.json"
    with open(parser_json_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_schema, f, indent=2, ensure_ascii=False)
    print(f"💾 Parser JSON saved to: {parser_json_path}")
    print()
    
    # ========================================================================
    # STEP 2: CHECK IF LLM FALLBACK NEEDED
    # ========================================================================
    print()
    print("┌" + "─" * 98 + "┐")
    print("│ STEP 2: QUALITY CHECK".ljust(99) + "│")
    print("└" + "─" * 98 + "┘")
    print()
    
    print(f"Confidence Score: {parser_confidence:.1%} (threshold: <50%)")
    print(f"Completeness Score: {parser_completeness:.1%} (threshold: <60%)")
    print()
    
    needs_llm_fallback = parser_confidence < 0.5 or parser_completeness < 0.6
    
    if needs_llm_fallback:
        print("⚠️  QUALITY CHECK FAILED - LLM Fallback will be triggered")
        print(f"   Reason: Confidence {parser_confidence:.1%} < 50% OR Completeness {parser_completeness:.1%} < 60%")
    else:
        print("✅ QUALITY CHECK PASSED - No LLM Fallback needed")
    print()
    
    # ========================================================================
    # STEP 3: LLM FALLBACK EXTRACTION (if needed)
    # ========================================================================
    if needs_llm_fallback:
        print()
        print("┌" + "─" * 98 + "┐")
        print("│ STEP 3: LLM FALLBACK EXTRACTION (GPT-4o)".ljust(99) + "│")
        print("└" + "─" * 98 + "┘")
        print()
        
        # Extract full text
        print("Extracting full text from PDF...")
        full_text, metadata = parser.extract_text_multimethod(pdf_path)
        
        print(f"✅ Full text extracted: {len(full_text):,} characters, {len(full_text.split()):,} words")
        print()
        
        # Prepare LLM prompt
        system_prompt = """You are a clinical trial data extraction expert with deep knowledge of clinical trial protocols.

Your task is to extract structured information from the clinical trial document and create a comprehensive JSON output.

**CRITICAL REQUIREMENTS:**
1. Extract EXACT text from the original document - do NOT paraphrase or summarize
2. Include page references, section numbers, or table numbers where information was found
3. Preserve all technical terminology, drug names, dosages, and measurements exactly as written
4. If information spans multiple sections, include all relevant content
5. For tables and structured data, preserve the original format and values
6. Include protocol version, date, and document identifiers when available

**Required Fields to Extract:**

1. **study_overview**: Extract title, NCT ID, protocol number, version, date, phase, study type, disease/indication
   
2. **brief_description**: Extract the study's brief summary or background section (first 500-1000 words)

3. **primary_secondary_objectives**: Extract primary and secondary endpoints with exact outcome measures, time frames, and definitions. Include both efficacy and safety objectives.

4. **treatment_arms_interventions**: Extract all treatment arms, drug names, doses, schedules, administration routes, and combination therapies. Include dosing tables if present.

5. **eligibility_criteria**: Extract complete inclusion and exclusion criteria lists with specific values (age ranges, lab values, prior treatments, etc.)

6. **enrollment_participant_flow**: Extract target enrollment, actual enrollment, patient disposition, screening numbers, and completion rates

7. **adverse_events_profile**: Extract adverse event tables, serious adverse events, Grade 3+ events, and safety monitoring procedures

8. **study_locations**: Extract site names, cities, countries, principal investigators, and contact information

9. **sponsor_information**: Extract sponsor name, medical monitor, CRO information, and collaborators

**Output Format:**
Return a valid JSON object with the structure:
{
  "study_overview": "EXACT TEXT with [Page X, Section Y] citations",
  "brief_description": "EXACT TEXT with citations",
  "primary_secondary_objectives": "EXACT TEXT with citations",
  "treatment_arms_interventions": "EXACT TEXT with citations",
  "eligibility_criteria": "EXACT TEXT with citations",
  "enrollment_participant_flow": "EXACT TEXT with citations",
  "adverse_events_profile": "EXACT TEXT with citations",
  "study_locations": "EXACT TEXT with citations",
  "sponsor_information": "EXACT TEXT with citations"
}

If a field cannot be found in the document, use null instead of an empty string.
IMPORTANT: Return ONLY the JSON object, no additional text or explanations."""

        user_prompt = f"""Clinical Trial Document (Full Text):

{full_text}

---

Please extract all required fields following the instructions. Include exact text with citations."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # Call LLM with retry logic for rate limits
        print("🤖 Calling GPT-4o-mini for extraction (this may take several minutes)...")
        print(f"   Document size: {len(full_text):,} chars (~{len(full_text)//4:,} tokens)")
        
        # Check if document might exceed rate limits (rough estimate: 4 chars per token)
        estimated_tokens = len(full_text) // 4
        if estimated_tokens > 100000:
            print(f"⚠️  WARNING: Document is very large ({estimated_tokens:,} tokens)")
            print(f"   This may take 5-10 minutes and could hit rate limits")
            print(f"   Consider upgrading your OpenAI tier for higher limits")
        
        print()
        
        try:
            response = llm.invoke(messages)
            print(f"✅ GPT-4o-mini response received: {len(response.content):,} characters")
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print(f"❌ Rate limit error: {str(e)}")
                print()
                print("💡 SOLUTIONS:")
                print("   1. Wait 60 seconds and try again")
                print("   2. Upgrade your OpenAI account tier for higher limits")
                print("   3. Use a shorter document (<500 pages)")
                print("   4. Contact OpenAI to increase your TPM limit")
                raise
            else:
                raise
        
        print()
        
        # Parse JSON
        try:
            response_content = response.content.strip()
            
            # Remove markdown code blocks
            if response_content.startswith('```json'):
                response_content = response_content[7:]
            if response_content.startswith('```'):
                response_content = response_content[3:]
            if response_content.endswith('```'):
                response_content = response_content[:-3]
            
            llm_extracted = json.loads(response_content.strip())
            
            print("✅ JSON parsed successfully")
            print()
            
            # Calculate metrics for LLM output
            llm_confidence, llm_completeness, llm_missing = calculate_metrics(llm_extracted)
            
            print("📊 LLM EXTRACTION METRICS:")
            print(f"   Confidence Score: {llm_confidence:.1%}")
            print(f"   Completeness Score: {llm_completeness:.1%}")
            print(f"   Missing Fields: {llm_missing}")
            print()
            
            print("📋 LLM EXTRACTED DATA:")
            print("-" * 100)
            
            total_llm_words = 0
            total_llm_chars = 0
            
            for field, value in llm_extracted.items():
                if value and value != "null" and isinstance(value, str) and value.strip():
                    word_count = len(value.split())
                    char_count = len(value)
                    total_llm_words += word_count
                    total_llm_chars += char_count
                    
                    # Show preview
                    preview = value[:150].replace('\n', ' ').strip()
                    if len(value) > 150:
                        preview += "..."
                    
                    print(f"\n{field}:")
                    print(f"   Words: {word_count:,} | Chars: {char_count:,}")
                    print(f"   Preview: {preview}")
                else:
                    print(f"\n{field}:")
                    print(f"   ❌ EMPTY or null")
            
            print()
            print(f"📈 TOTAL LLM OUTPUT: {total_llm_words:,} words, {total_llm_chars:,} characters")
            print()
            
            # Save LLM JSON
            llm_json_path = f"{Path(pdf_path).stem}_llm_output.json"
            with open(llm_json_path, 'w', encoding='utf-8') as f:
                json.dump(llm_extracted, f, indent=2, ensure_ascii=False)
            print(f"💾 LLM JSON saved to: {llm_json_path}")
            print()
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Response preview: {response.content[:500]}")
            llm_extracted = None
            llm_confidence = 0
            llm_completeness = 0
            llm_missing = list(parsed_schema.keys())
    else:
        llm_extracted = None
        llm_confidence = None
        llm_completeness = None
        llm_missing = None
    
    # ========================================================================
    # STEP 4: COMPARISON
    # ========================================================================
    print()
    print("┌" + "─" * 98 + "┐")
    print("│ STEP 4: SIDE-BY-SIDE COMPARISON".ljust(99) + "│")
    print("└" + "─" * 98 + "┘")
    print()
    
    print(f"{'Field':<35} | {'Parser Words':<15} | {'LLM Words':<15} | {'Improvement':<15}")
    print("-" * 100)
    
    for field in parsed_schema.keys():
        parser_val = parsed_schema.get(field, "")
        parser_words = len(parser_val.split()) if parser_val and isinstance(parser_val, str) else 0
        
        if llm_extracted:
            llm_val = llm_extracted.get(field, "")
            llm_words = len(llm_val.split()) if llm_val and isinstance(llm_val, str) and llm_val != "null" else 0
            improvement = llm_words - parser_words
            improvement_str = f"+{improvement}" if improvement > 0 else str(improvement)
        else:
            llm_words = "N/A"
            improvement_str = "N/A"
        
        print(f"{field:<35} | {str(parser_words):<15} | {str(llm_words):<15} | {improvement_str:<15}")
    
    print()
    print("📊 OVERALL COMPARISON:")
    print(f"{'Metric':<35} | {'Parser':<15} | {'LLM':<15} | {'Change':<15}")
    print("-" * 100)
    print(f"{'Confidence Score':<35} | {f'{parser_confidence:.1%}':<15} | {f'{llm_confidence:.1%}' if llm_confidence is not None else 'N/A':<15} | {f'{(llm_confidence - parser_confidence):.1%}' if llm_confidence is not None else 'N/A':<15}")
    print(f"{'Completeness Score':<35} | {f'{parser_completeness:.1%}':<15} | {f'{llm_completeness:.1%}' if llm_completeness is not None else 'N/A':<15} | {f'{(llm_completeness - parser_completeness):.1%}' if llm_completeness is not None else 'N/A':<15}")
    print(f"{'Missing Fields':<35} | {len(parser_missing):<15} | {len(llm_missing) if llm_missing is not None else 'N/A':<15} | {len(parser_missing) - len(llm_missing) if llm_missing is not None else 'N/A':<15}")
    
    print()
    print("=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)
    print()
    
    return {
        "parser": {
            "data": parsed_schema,
            "confidence": parser_confidence,
            "completeness": parser_completeness,
            "missing": parser_missing
        },
        "llm": {
            "data": llm_extracted,
            "confidence": llm_confidence,
            "completeness": llm_completeness,
            "missing": llm_missing
        } if llm_extracted else None
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to first available PDF
        pdfs = [
            "Prot_000.pdf",
            "HIV-HIV-2019-Venter-ADVANCE.pdf",
            "HIV-HIV-2018-Molloy-A-randomised-controlled-trial-of.pdf"
        ]
        
        pdf_path = None
        for pdf in pdfs:
            if os.path.exists(pdf):
                pdf_path = pdf
                break
        
        if not pdf_path:
            print("❌ No PDF found. Please specify a PDF path:")
            print(f"   python detailed_diagnostics.py <path_to_pdf>")
            sys.exit(1)
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)
    
    # Run analysis
    results = analyze_pdf_step_by_step(pdf_path)
    
    print()
    print("📁 Output files generated:")
    print(f"   - {Path(pdf_path).stem}_parser_output.json (Parser extraction)")
    if results['llm']:
        print(f"   - {Path(pdf_path).stem}_llm_output.json (LLM extraction)")
