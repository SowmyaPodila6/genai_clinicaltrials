"""
Clinical Trial PDF Parser
Parses PDF documents and organizes content by section headers
"""

import re
import difflib
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import pdfplumber
import PyPDF2
from io import BytesIO
from pathlib import Path
try:
    from pypdf import PdfReader as PyPDFReader
except ImportError:
    PyPDFReader = None


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClinicalTrialPDFParser:
    """
    A parser for clinical trial PDF documents that extracts and organizes content by section headers.
    """
    
    def __init__(self):
        """Initialize the parser with common clinical trial section patterns."""
        self.section_patterns = [
            # Common clinical trial section headers (case insensitive, flexible)
            r'^\s*(?:ABSTRACT|Abstract)\s*$',
            r'^\s*(?:INTRODUCTION|Introduction)\s*$',
            r'^\s*(?:BACKGROUND|Background)\s*$',
            r'^\s*(?:METHODS|Methods|METHODOLOGY|Methodology)\s*$',
            r'^\s*(?:MATERIALS AND METHODS|Materials and Methods)\s*$',
            r'^\s*(?:STUDY DESIGN|Study Design)\s*$',
            r'^\s*(?:PARTICIPANTS|Participants|SUBJECTS|Subjects)\s*$',
            r'^\s*(?:RESULTS|Results)\s*$',
            r'^\s*(?:FINDINGS|Findings)\s*$',
            r'^\s*(?:DISCUSSION|Discussion)\s*$',
            r'^\s*(?:CONCLUSIONS?|Conclusions?)\s*$',
            r'^\s*(?:REFERENCES|References|BIBLIOGRAPHY|Bibliography)\s*$',
            r'^\s*(?:ACKNOWLEDGMENTS?|Acknowledgments?)\s*$',
            r'^\s*(?:APPENDIX|Appendix|APPENDICES|Appendices)\s*$',
            r'^\s*(?:LIMITATIONS|Limitations)\s*$',
            r'^\s*(?:STATISTICAL ANALYSIS|Statistical Analysis)\s*$',
            r'^\s*(?:ETHICS|Ethics|ETHICAL CONSIDERATIONS|Ethical Considerations)\s*$',
            r'^\s*(?:CONFLICTS OF INTEREST|Conflicts of Interest)\s*$',
            r'^\s*(?:FUNDING|Funding)\s*$',
            # Numbered sections
            r'^\s*\d+\.?\s+[A-Z][A-Za-z\s]+\s*$',
            # Roman numeral sections
            r'^\s*[IVX]+\.?\s+[A-Z][A-Za-z\s]+\s*$',
            # Common section headers that might be in all caps or title case
            r'^\s*[A-Z][A-Z\s]{2,20}\s*$',  # All caps words
        ]
        
        # Compile patterns for better performance
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE | re.IGNORECASE) for pattern in self.section_patterns]
    
    def extract_text_with_pdfplumber(self, file_path: str) -> str:
        """
        Extract text from PDF using pdfplumber (better for complex layouts).
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with pdfplumber: {e}")
            return ""
    
    def extract_text_with_pypdf(self, file_path: str) -> str:
        """
        Extract text from PDF using pypdf (modern PyPDF).
        """
        if not PyPDFReader:
            logger.error("pypdf is not installed.")
            return ""
        try:
            text = ""
            reader = PyPDFReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with pypdf: {e}")
            return ""
        """
        Extract text from PDF using PyPDF2 (fallback method).
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with PyPDF2: {e}")
            return ""
    
    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes using pdfplumber.
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Extracted text as string
        """
        try:
            text = ""
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from bytes: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing extra whitespace and formatting issues.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove page breaks and form feeds
        text = re.sub(r'[\f\r]', '\n', text)
        # Normalize line breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    
    def identify_section_headers(self, text: str) -> List[Tuple[str, int]]:
        """
        Identify section headers in the text using predefined patterns.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of tuples containing (header_text, position)
        """
        headers = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check against all patterns
            for pattern in self.compiled_patterns:
                if pattern.match(line):
                    # Calculate approximate character position
                    position = sum(len(lines[j]) + 1 for j in range(i))
                    headers.append((line, position))
                    break
        
        # Remove duplicates and sort by position
        headers = list(set(headers))
        headers.sort(key=lambda x: x[1])
        
        return headers
    
    def parse_by_sections(self, text: str) -> Dict[str, str]:
        """
        Parse text and organize content by section headers.
        
        Args:
            text: Text to parse
            
        Returns:
            Dictionary with section headers as keys and content as values
        """
        # Clean the text first
        text = self.clean_text(text)
        
        # Identify section headers
        headers = self.identify_section_headers(text)
        
        if not headers:
            logger.warning("No section headers found. Returning full text as 'Content'.")
            return {"Content": text}
        
        sections = {}
        
        for i, (header, position) in enumerate(headers):
            # Determine the end position for this section
            if i + 1 < len(headers):
                next_position = headers[i + 1][1]
                section_text = text[position:next_position]
            else:
                section_text = text[position:]
            
            # Remove the header from the section content
            lines = section_text.split('\n')
            if lines and lines[0].strip() == header:
                section_content = '\n'.join(lines[1:])
            else:
                section_content = section_text
            
            # Clean up the section content
            section_content = section_content.strip()
            
            if section_content:
                sections[header] = section_content
        
        return sections
    
    def parse_pdf_file(self, file_path: str, use_fallback: bool = True) -> Dict[str, str]:
        """
        Parse a PDF file and return content organized by sections.
        
        Args:
            file_path: Path to the PDF file
            use_fallback: Whether to use PyPDF2 as fallback if pdfplumber fails
            
        Returns:
            Dictionary with section headers as keys and content as values
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Parsing PDF file: {file_path}")
        
    # docling/GROBID not used; rely on pdfplumber/pypdf and heuristics
        # Try pdfplumber
        text = self.extract_text_with_pdfplumber(file_path)
        # Try pypdf if pdfplumber fails
        if not text and use_fallback:
            logger.warning("pdfplumber extraction failed, trying pypdf...")
            text = self.extract_text_with_pypdf(file_path)
        if not text:
            raise ValueError("Could not extract text from PDF file")
        return self.parse_by_sections(text)
    def extract_tables_with_pdfplumber(self, file_path: str) -> list:
        """
        Extract tables from PDF using pdfplumber.
        Returns a list of tables (each table is a list of rows).
        """
        tables = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
        return tables
    
    def parse_pdf_bytes(self, pdf_bytes: bytes) -> Dict[str, str]:
        """
        Parse PDF from bytes and return content organized by sections.
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Dictionary with section headers as keys and content as values
        """
        logger.info("Parsing PDF from bytes")
        
        text = self.extract_text_from_bytes(pdf_bytes)
        
        if not text:
            raise ValueError("Could not extract text from PDF bytes")
        
        return self.parse_by_sections(text)
    
    def get_section_summary(self, sections: Dict[str, str]) -> Dict[str, int]:
        """
        Get a summary of sections with word counts.
        
        Args:
            sections: Dictionary of sections
            
        Returns:
            Dictionary with section names and word counts
        """
        summary = {}
        for section_name, content in sections.items():
            word_count = len(content.split())
            summary[section_name] = word_count
        
        return summary
    
    def search_sections(self, sections: Dict[str, str], search_term: str, case_sensitive: bool = False) -> Dict[str, List[str]]:
        """
        Search for a term across all sections.
        
        Args:
            sections: Dictionary of sections
            search_term: Term to search for
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            Dictionary with section names and matching sentences
        """
        results = {}
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for section_name, content in sections.items():
            sentences = re.split(r'[.!?]+', content)
            matching_sentences = []
            
            for sentence in sentences:
                if re.search(re.escape(search_term), sentence, flags):
                    matching_sentences.append(sentence.strip())
            
            if matching_sentences:
                results[section_name] = matching_sentences
        
        return results

def map_sections_to_schema(sections: dict, tables: list = None) -> dict:
    """
    Enhanced mapping of parsed PDF sections to the required clinical trial JSON schema using robust heuristics, synonyms, and fallback strategies.
    Only the 9 required fields are included, in the correct order, and all extra fields are omitted.
    """
    schema_fields = [
        ("Study Overview", ["overview", "summary", "study overview", "background", "abstract", "study summary", "purpose", "rationale", "synopsis"]),
        ("Brief Description", ["brief description", "summary", "abstract", "background", "introduction", "study description", "short description", "overview"]),
        ("Primary and Secondary Objectives", ["objective", "objectives", "aim", "purpose", "goal", "primary objective", "secondary objective", "study objective", "endpoints", "outcomes"]),
        ("Treatment Arms and Interventions", ["treatment", "intervention", "arms", "methods", "study design", "treatment arms", "interventions", "study groups", "regimen", "protocol"]),
        ("Eligibility Criteria", ["eligibility", "criteria", "inclusion", "exclusion", "participants", "subjects", "eligibility criteria", "inclusion criteria", "exclusion criteria", "patient selection"]),
        ("Enrollment and Participant Flow", ["enrollment", "participant flow", "recruitment", "sample size", "population", "enrolment", "participant disposition", "flow of participants", "study population", "randomization"]),
        ("Adverse Events Profile", ["adverse event", "safety", "side effect", "tolerability", "complication", "adverse events", "safety results", "side effects", "harms", "risk profile", "safety profile"]),
        ("Study Locations", ["location", "site", "center", "hospital", "clinic", "study locations", "investigational sites", "centres", "study sites"]),
        ("Sponsor Information", ["sponsor", "funding", "support", "acknowledgment", "acknowledgement", "funding source", "study sponsor", "financial support", "sponsorship"]),
    ]

    def robust_find(keys, fallback=""):
        # Try exact and partial match first
        for k in keys:
            for sec in sections:
                if k.lower() in sec.lower():
                    return sections[sec]
        # Fuzzy match
        all_headers = list(sections.keys())
        for k in keys:
            matches = difflib.get_close_matches(k, all_headers, n=1, cutoff=0.5)
            if matches:
                return sections[matches[0]]
        # Try to find in the first N lines of the document if all else fails
        if "Content" in sections:
            content = sections["Content"]
            for k in keys:
                idx = content.lower().find(k.lower())
                if idx != -1:
                    # Return a snippet around the found keyword
                    snippet = content[max(0, idx-100):idx+400]
                    return snippet
        return fallback

    result = {}
    for field, keys in schema_fields:
        result[field] = robust_find(keys)
    return result

def parse_all_pdfs_in_folder(folder_path: str, as_schema: bool = False) -> dict:
    """
    Parse all PDF files in a folder and return a dict of filename to parsed sections and tables.
    """
    parser = ClinicalTrialPDFParser()
    results = {}
    pdf_files = list(Path(folder_path).glob("*.pdf"))
    for pdf_file in pdf_files:
        try:
            sections = parser.parse_pdf_file(str(pdf_file))
            tables = parser.extract_tables_with_pdfplumber(str(pdf_file))
            if as_schema:
                results[pdf_file.name] = map_sections_to_schema(sections, tables)
            else:
                results[pdf_file.name] = {
                    "sections": sections,
                    "tables": tables
                }
        except Exception as e:
            logger.error(f"Failed to parse {pdf_file}: {e}")
    return results

def main():
    """
    Example usage of the ClinicalTrialPDFParser.
    """
    parser = ClinicalTrialPDFParser()
    
    # Example: Parse all PDFs in the folder and print as clinical trial schema JSON
    try:
        folder = "."
        results = parse_all_pdfs_in_folder(folder, as_schema=True)
        import json
        output_file = "parsed_clinical_trials.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved parsed results to {output_file}")
    except Exception as e:
        print(f"Error parsing PDFs: {e}")


if __name__ == "__main__":
    main()