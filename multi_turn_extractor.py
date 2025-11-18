"""
Multi-Turn PDF Extraction Strategy
====================================

Splits large PDFs into smaller chunks and processes them across multiple LLM calls
to avoid rate limiting while maintaining context and quality.

Key Features:
- Field-based chunking: Extract one field at a time
- Smart context windows: Include relevant surrounding text
- Rate limit management: Automatic delays and retries
- Progress tracking: Real-time updates for UI
- Result merging: Intelligent combination of partial results

Author: Clinical Trials AI Team
Version: 1.0.0
"""

import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import tiktoken
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    chunk_id: str
    field_name: str
    start_char: int
    end_char: int
    estimated_tokens: int
    context_before: str
    context_after: str


class MultiTurnExtractor:
    """
    Extracts clinical trial data using multiple LLM calls to avoid rate limits.
    
    Strategy:
    1. Split document into field-specific chunks
    2. Process each chunk with its own LLM call
    3. Merge results intelligently
    4. Handle rate limits with automatic retries
    """
    
    # Field definitions with extraction hints
    FIELD_CONFIGS = {
        "study_overview": {
            "keywords": ["protocol", "study design", "overview", "summary", "background", "rationale"],
            "max_tokens": 40000,
            "priority": 1
        },
        "brief_description": {
            "keywords": ["description", "purpose", "aims", "goals"],
            "max_tokens": 30000,
            "priority": 2
        },
        "primary_secondary_objectives": {
            "keywords": ["objective", "endpoint", "primary outcome", "secondary outcome", "aim"],
            "max_tokens": 35000,
            "priority": 1
        },
        "treatment_arms_interventions": {
            "keywords": ["treatment", "intervention", "arm", "group", "therapy", "dose", "regimen"],
            "max_tokens": 40000,
            "priority": 1
        },
        "eligibility_criteria": {
            "keywords": ["eligibility", "inclusion", "exclusion", "criteria", "participant"],
            "max_tokens": 35000,
            "priority": 2
        },
        "enrollment_participant_flow": {
            "keywords": ["enrollment", "randomization", "participant flow", "screening", "allocation"],
            "max_tokens": 35000,
            "priority": 2
        },
        "adverse_events_profile": {
            "keywords": ["adverse event", "safety", "toxicity", "side effect", "AE", "SAE"],
            "max_tokens": 50000,
            "priority": 1
        },
        "study_locations": {
            "keywords": ["site", "location", "center", "institution", "investigator"],
            "max_tokens": 25000,
            "priority": 3
        },
        "sponsor_information": {
            "keywords": ["sponsor", "funding", "organization", "contact", "investigator"],
            "max_tokens": 20000,
            "priority": 3
        }
    }
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens_per_call: int = 180000,  # Leave buffer under 200k limit
        delay_between_calls: float = 2.0  # Seconds
    ):
        """Initialize the multi-turn extractor."""
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.max_tokens_per_call = max_tokens_per_call
        self.delay_between_calls = delay_between_calls
        self.encoding = tiktoken.encoding_for_model(model)
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def analyze_document_chunking(self, full_text: str) -> Dict[str, Any]:
        """
        Analyze how the document would be chunked for each field.
        Returns statistics without actually performing extraction.
        
        Returns:
            Dictionary with chunking analysis for each field
        """
        analysis = {
            "total_document_chars": len(full_text),
            "total_document_tokens": self.count_tokens(full_text),
            "fields": {}
        }
        
        for field_name, config in self.FIELD_CONFIGS.items():
            relevant_sections = self.find_relevant_sections(full_text, field_name, config)
            
            # Calculate how many sections would fit
            sections_that_fit = 0
            total_tokens_used = 0
            max_tokens = config["max_tokens"]
            
            for start, end, score in relevant_sections:
                section_text = full_text[start:end]
                section_tokens = self.count_tokens(section_text)
                
                if total_tokens_used + section_tokens <= max_tokens:
                    sections_that_fit += 1
                    total_tokens_used += section_tokens
                else:
                    break
            
            analysis["fields"][field_name] = {
                "keywords": config["keywords"],
                "max_tokens_allowed": max_tokens,
                "sections_found": len(relevant_sections),
                "sections_that_fit": sections_that_fit,
                "tokens_used": total_tokens_used,
                "utilization_pct": (total_tokens_used / max_tokens) * 100 if max_tokens > 0 else 0,
                "top_relevance_scores": [s[2] for s in relevant_sections[:5]] if relevant_sections else []
            }
        
        return analysis
    
    def print_chunking_analysis(self, full_text: str):
        """Print a readable analysis of document chunking."""
        analysis = self.analyze_document_chunking(full_text)
        
        print("\n" + "="*80)
        print("📊 DOCUMENT CHUNKING ANALYSIS")
        print("="*80)
        print(f"📄 Total Document: {analysis['total_document_chars']:,} chars, {analysis['total_document_tokens']:,} tokens")
        print()
        
        for field_name, stats in analysis["fields"].items():
            print(f"\n🔹 {field_name.upper().replace('_', ' ')}")
            print(f"   Keywords: {', '.join(stats['keywords'])}")
            print(f"   Max tokens allowed: {stats['max_tokens_allowed']:,}")
            print(f"   Sections found: {stats['sections_found']}")
            print(f"   Sections that fit: {stats['sections_that_fit']}")
            print(f"   Tokens used: {stats['tokens_used']:,} ({stats['utilization_pct']:.1f}% utilization)")
            if stats['top_relevance_scores']:
                print(f"   Top relevance scores: {stats['top_relevance_scores']}")
        
        print("\n" + "="*80 + "\n")

    
    def find_relevant_sections(
        self,
        full_text: str,
        field_name: str,
        config: Dict[str, Any]
    ) -> List[Tuple[int, int, float]]:
        """
        Find sections of text relevant to a specific field.
        
        Returns:
            List of (start_pos, end_pos, relevance_score) tuples
        """
        keywords = config["keywords"]
        sections = []
        
        # Split text into paragraphs
        paragraphs = full_text.split('\n\n')
        current_pos = 0
        
        logger.info(f"🔍 Searching for '{field_name}' using keywords: {keywords}")
        logger.info(f"📄 Total paragraphs to scan: {len(paragraphs)}")
        
        for para in paragraphs:
            para_lower = para.lower()
            
            # Calculate relevance score
            score = 0
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in para_lower:
                    count = para_lower.count(keyword.lower())
                    score += count
                    matched_keywords.append(f"{keyword}({count})")
            
            if score > 0:
                start = current_pos
                end = current_pos + len(para)
                sections.append((start, end, score))
                # Log first few high-scoring sections for debugging
                if score >= 3:
                    preview = para[:100].replace('\n', ' ')
                    logger.debug(f"  ✓ Found section (score={score}): {preview}... [keywords: {', '.join(matched_keywords)}]")
            
            current_pos += len(para) + 2  # +2 for \n\n
        
        # Sort by relevance score (descending)
        sections.sort(key=lambda x: x[2], reverse=True)
        
        logger.info(f"✅ Found {len(sections)} relevant sections for '{field_name}'")
        if sections:
            top_5_scores = [s[2] for s in sections[:5]]
            logger.info(f"   Top 5 relevance scores: {top_5_scores}")
        
        return sections
    
    def create_field_chunk(
        self,
        full_text: str,
        field_name: str,
        max_tokens: int
    ) -> str:
        """
        Create a focused chunk for extracting a specific field.
        
        Strategy:
        1. Find sections with relevant keywords
        2. Include high-relevance sections first
        3. Add context until token limit reached
        """
        config = self.FIELD_CONFIGS[field_name]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📦 Creating chunk for: {field_name}")
        logger.info(f"🎯 Max tokens allowed: {max_tokens:,}")
        
        # Find relevant sections
        relevant_sections = self.find_relevant_sections(full_text, field_name, config)
        
        if not relevant_sections:
            # If no keywords found, use first N tokens
            logger.warning(f"⚠️  No relevant sections found for {field_name}, using beginning of document")
            chunk_text = full_text
        else:
            # Combine relevant sections
            chunk_parts = []
            current_tokens = 0
            sections_included = 0
            
            logger.info(f"📊 Combining sections (highest relevance first)...")
            
            for start, end, score in relevant_sections:
                section_text = full_text[start:end]
                section_tokens = self.count_tokens(section_text)
                
                if current_tokens + section_tokens > max_tokens:
                    logger.info(f"   ⛔ Stopped at section {sections_included + 1}: would exceed token limit")
                    logger.info(f"      (needed {section_tokens:,} more tokens, only {max_tokens - current_tokens:,} available)")
                    break
                
                chunk_parts.append(section_text)
                current_tokens += section_tokens
                sections_included += 1
                
                # Log first few sections being included
                if sections_included <= 5:
                    preview = section_text[:80].replace('\n', ' ')
                    logger.info(f"   ✓ Section {sections_included} (score={score}, tokens={section_tokens:,}): {preview}...")
            
            chunk_text = "\n\n".join(chunk_parts)
            
            logger.info(f"✅ Combined {sections_included} sections into chunk")
            logger.info(f"📏 Initial chunk size: {current_tokens:,} tokens ({len(chunk_text):,} chars)")
        
        # Truncate if still too long
        truncation_count = 0
        while self.count_tokens(chunk_text) > max_tokens:
            # Remove last 10% of text
            chunk_text = chunk_text[:int(len(chunk_text) * 0.9)]
            truncation_count += 1
        
        if truncation_count > 0:
            logger.warning(f"⚠️  Truncated chunk {truncation_count} times to fit token limit")
        
        final_tokens = self.count_tokens(chunk_text)
        logger.info(f"📦 Final chunk: {final_tokens:,} tokens ({len(chunk_text):,} chars)")
        logger.info(f"   Utilization: {(final_tokens/max_tokens)*100:.1f}% of allowed tokens")
        logger.info(f"{'='*60}\n")
        
        return chunk_text
    
    def extract_field(
        self,
        chunk_text: str,
        field_name: str,
        field_description: str
    ) -> Optional[str]:
        """
        Extract a single field using LLM.
        
        Args:
            chunk_text: Focused text chunk for this field
            field_name: Name of the field to extract
            field_description: Description of what to extract
            
        Returns:
            Extracted field value or None
        """
        system_prompt = f"""You are an expert at extracting clinical trial information from PDF documents.

Extract ONLY the following field from the provided text:
**{field_name}**: {field_description}

CRITICAL INSTRUCTIONS:
1. Extract EXACTLY what is asked for, nothing more
2. Include ALL relevant details from the text
3. Cite page numbers when mentioned
4. If information is not found, return "Not found in provided text"
5. Be comprehensive but focused on this specific field
6. Use the exact terminology from the source document

Return ONLY the extracted content, no explanations."""

        user_prompt = f"""Extract **{field_name}** from this clinical trial document:

{chunk_text}

Return the extracted information:"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            content = response.content.strip()
            
            # Check if extraction failed
            if content.lower() in ["not found", "n/a", "none", "not available", "not found in provided text"]:
                return None
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting {field_name}: {e}")
            return None
    
    def extract_all_fields(
        self,
        full_text: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, str]:
        """
        Extract all fields using multi-turn strategy.
        
        Args:
            full_text: Complete PDF text
            progress_callback: Function to call with (field_name, progress, total)
            
        Returns:
            Dictionary of extracted fields
        """
        results = {}
        total_fields = len(self.FIELD_CONFIGS)
        
        # Field descriptions (same as in langgraph_workflow.py)
        field_descriptions = {
            "study_overview": "Study title, NCT ID, phase, design type (randomized/controlled/blinded), study duration",
            "brief_description": "2-3 sentence summary of the study purpose and design",
            "primary_secondary_objectives": "Primary endpoints/objectives and secondary endpoints/objectives with definitions",
            "treatment_arms_interventions": "All treatment arms, interventions, dosing schedules, and administration details",
            "eligibility_criteria": "Inclusion criteria and exclusion criteria for participants",
            "enrollment_participant_flow": "Target enrollment number, actual enrollment, randomization details, participant flow",
            "adverse_events_profile": "Common adverse events with frequencies, serious adverse events, and safety data",
            "study_locations": "Study sites, countries, and principal investigators",
            "sponsor_information": "Primary sponsor, collaborators, and funding sources"
        }
        
        # Sort fields by priority
        sorted_fields = sorted(
            self.FIELD_CONFIGS.items(),
            key=lambda x: x[1]["priority"]
        )
        
        for idx, (field_name, config) in enumerate(sorted_fields, 1):
            logger.info(f"Extracting field {idx}/{total_fields}: {field_name}")
            
            if progress_callback:
                progress_callback(field_name, idx, total_fields)
            
            # Create focused chunk for this field
            chunk_text = self.create_field_chunk(
                full_text,
                field_name,
                config["max_tokens"]
            )
            
            # Extract the field
            field_value = self.extract_field(
                chunk_text,
                field_name,
                field_descriptions[field_name]
            )
            
            if field_value:
                results[field_name] = field_value
                logger.info(f"✅ Extracted {field_name}: {len(field_value)} chars")
            else:
                results[field_name] = ""
                logger.warning(f"⚠️  No data found for {field_name}")
            
            # Rate limit management: wait between calls
            if idx < total_fields:
                time.sleep(self.delay_between_calls)
        
        return results
    
    def extract_with_retry(
        self,
        full_text: str,
        progress_callback: Optional[callable] = None,
        max_retries: int = 3
    ) -> Dict[str, str]:
        """
        Extract all fields with automatic retry on failures.
        
        Args:
            full_text: Complete PDF text
            progress_callback: Progress update function
            max_retries: Maximum retry attempts per field
            
        Returns:
            Dictionary of extracted fields
        """
        results = {}
        
        for field_name in self.FIELD_CONFIGS.keys():
            for attempt in range(max_retries):
                try:
                    # Get existing results to pass to callback
                    total = len(self.FIELD_CONFIGS)
                    current = len(results) + 1
                    
                    if progress_callback:
                        progress_callback(field_name, current, total)
                    
                    # Create chunk and extract
                    config = self.FIELD_CONFIGS[field_name]
                    chunk_text = self.create_field_chunk(
                        full_text,
                        field_name,
                        config["max_tokens"]
                    )
                    
                    field_descriptions = {
                        "study_overview": "Study title, NCT ID, phase, design type (randomized/controlled/blinded), study duration",
                        "brief_description": "2-3 sentence summary of the study purpose and design",
                        "primary_secondary_objectives": "Primary endpoints/objectives and secondary endpoints/objectives with definitions",
                        "treatment_arms_interventions": "All treatment arms, interventions, dosing schedules, and administration details",
                        "eligibility_criteria": "Inclusion criteria and exclusion criteria for participants",
                        "enrollment_participant_flow": "Target enrollment number, actual enrollment, randomization details, participant flow",
                        "adverse_events_profile": "Common adverse events with frequencies, serious adverse events, and safety data",
                        "study_locations": "Study sites, countries, and principal investigators",
                        "sponsor_information": "Primary sponsor, collaborators, and funding sources"
                    }
                    
                    field_value = self.extract_field(
                        chunk_text,
                        field_name,
                        field_descriptions[field_name]
                    )
                    
                    results[field_name] = field_value if field_value else ""
                    logger.info(f"✅ Extracted {field_name} (attempt {attempt + 1})")
                    break  # Success, move to next field
                    
                except Exception as e:
                    logger.warning(f"⚠️  Attempt {attempt + 1} failed for {field_name}: {e}")
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        wait_time = self.delay_between_calls * (2 ** attempt)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        # All retries failed
                        results[field_name] = ""
                        logger.error(f"❌ Failed to extract {field_name} after {max_retries} attempts")
            
            # Small delay between fields
            time.sleep(self.delay_between_calls)
        
        return results


def estimate_extraction_cost(full_text: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """
    Estimate the cost and time for multi-turn extraction.
    
    Returns:
        Dictionary with cost, time, and token estimates
    """
    encoding = tiktoken.encoding_for_model(model)
    total_tokens = len(encoding.encode(full_text))
    
    # Cost per million tokens (as of Nov 2024)
    costs = {
        "gpt-4o-mini": {"input": 0.150, "output": 0.600},
        "gpt-4o": {"input": 2.50, "output": 10.00}
    }
    
    # Estimate: each field uses ~20% of doc + generates ~500 tokens
    num_fields = 9
    input_tokens_per_field = int(total_tokens * 0.3)  # 30% overlap for context
    output_tokens_per_field = 500
    
    total_input_tokens = input_tokens_per_field * num_fields
    total_output_tokens = output_tokens_per_field * num_fields
    
    model_costs = costs.get(model, costs["gpt-4o-mini"])
    
    input_cost = (total_input_tokens / 1_000_000) * model_costs["input"]
    output_cost = (total_output_tokens / 1_000_000) * model_costs["output"]
    total_cost = input_cost + output_cost
    
    # Time estimate: ~3-5 seconds per field + delays
    estimated_time = (num_fields * 4) + (num_fields * 2)  # processing + delays
    
    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "estimated_time_seconds": estimated_time,
        "estimated_time_minutes": estimated_time / 60,
        "num_fields": num_fields,
        "model": model
    }
