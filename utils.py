"""
Utility Functions for Clinical Trial Analysis
Database, PDF generation, and helper functions
"""

import sqlite3
import json
import unicodedata
from fpdf import FPDF
from typing import Dict, List, Tuple, Optional

# Database configuration
DB_FILE = "chat_history.db"


# ============================================================================
# Database Functions
# ============================================================================

def get_db_connection():
    """Create database connection and ensure table exists"""
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


def save_message_to_db(conversation_id: str, role: str, content: str):
    """Save a single message to the database"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, ?, ?)", 
              (conversation_id, role, content))
    conn.commit()
    conn.close()


def load_messages_from_db(conversation_id: str) -> List[Dict]:
    """Load all chat messages for a specific conversation"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_messages WHERE conversation_id = ? ORDER BY id", 
              (conversation_id,))
    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]
    conn.close()
    return messages


def get_all_conversations() -> List[str]:
    """Return list of all unique conversation IDs"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT conversation_id FROM chat_messages ORDER BY id DESC")
    conversations = [row[0] for row in c.fetchall()]
    conn.close()
    return conversations


# ============================================================================
# PDF Generation Functions
# ============================================================================

def clean_text_for_pdf(text: str) -> str:
    """Clean text for PDF generation by removing problematic Unicode characters"""
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
    """Custom PDF class with header and footer"""
    
    def __init__(self, nct_id: str):
        super().__init__()
        self.nct_id = nct_id
    
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, f'Clinical Trial Summary: {self.nct_id}', 0, 1, 'C')
        self.ln(3)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def write_wrapped_text(pdf: FPDF, text: str, font_size: int = 10, font_style: str = '', indent: int = 0):
    """Helper function to properly wrap text to full page width"""
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


def create_summary_pdf(summary_text: str, nct_id: str) -> bytes:
    """Create PDF from summary text"""
    try:
        pdf = CustomPDF(nct_id)
        pdf.add_page()
        pdf.set_margins(15, 25, 15)
        
        # Add URL link
        pdf.set_font("Arial", 'U', 10)
        url_text = f"https://clinicaltrials.gov/study/{nct_id}"
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 8, url_text, 0, 1, 'C', link=url_text)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)

        # Process summary content
        clean_summary = clean_text_for_pdf(summary_text)
        lines = clean_summary.split('\n')
        
        for line in lines:
            try:
                line = line.strip()
                if not line:
                    pdf.ln(3)
                    continue
                
                # Main headers (# )
                if line.startswith('# '):
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 16)
                    pdf.set_text_color(0, 51, 102)
                    header_text = clean_text_for_pdf(line.replace('# ', ''))
                    write_wrapped_text(pdf, header_text, 16, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(3)
                
                # Section headers (## )
                elif line.startswith('## '):
                    pdf.ln(6)
                    pdf.set_font("Arial", 'B', 14)
                    pdf.set_text_color(51, 102, 153)
                    header_text = clean_text_for_pdf(line.replace('## ', ''))
                    write_wrapped_text(pdf, header_text, 14, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(2)
                
                # Subsection headers (### )
                elif line.startswith('### '):
                    pdf.ln(4)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.set_text_color(102, 153, 204)
                    header_text = clean_text_for_pdf(line.replace('### ', ''))
                    write_wrapped_text(pdf, header_text, 12, 'B')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(2)
                
                # Bold text (**text**)
                elif '**' in line:
                    bold_text = clean_text_for_pdf(line.replace('**', ''))
                    write_wrapped_text(pdf, bold_text, 11, 'B')
                
                # Bullet points (• or -)
                elif line.startswith('• ') or line.startswith('- '):
                    bullet_text = clean_text_for_pdf(line)
                    write_wrapped_text(pdf, bullet_text, 10, '', 8)
                
                # Table rows (|)
                elif '|' in line and line.count('|') >= 2:
                    pdf.set_font("Arial", '', 9)
                    table_text = clean_text_for_pdf(line)
                    if len(table_text) > 120:
                        table_text = table_text[:117] + "..."
                    pdf.cell(0, 5, table_text, 0, 1, 'L')
                
                # Regular text
                else:
                    regular_text = clean_text_for_pdf(line)
                    if regular_text.strip():
                        write_wrapped_text(pdf, regular_text, 10, '')
                
            except Exception:
                continue

        return pdf.output(dest='S').encode('latin1', 'ignore')
        
    except Exception as e:
        # Fallback error PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "PDF Generation Error", ln=True)
        pdf.cell(0, 10, f"NCT ID: {nct_id}", ln=True)
        pdf.cell(0, 10, "Please download the summary as text instead.", ln=True)
        return pdf.output(dest='S').encode('latin1', 'ignore')


# ============================================================================
# Data Processing Functions
# ============================================================================

def calculate_metrics(data_dict: Dict) -> Tuple[float, float, List[str]]:
    """Calculate confidence and completeness scores for extracted data"""
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
    total_content = 0
    
    for field in required_fields:
        content = data_dict.get(field, "")
        if content and len(str(content).strip()) > 20:
            filled_fields += 1
            total_content += len(str(content))
        else:
            missing_fields.append(field)
    
    completeness_score = filled_fields / len(required_fields)
    
    # Confidence based on content richness
    avg_content_length = total_content / max(filled_fields, 1)
    confidence_score = min(1.0, avg_content_length / 500)
    
    return confidence_score, completeness_score, missing_fields


def filter_meaningful_sections(data_dict: Dict) -> Dict:
    """Filter out sections without meaningful content"""
    filtered = {}
    
    for section, content in data_dict.items():
        if (content and 
            content != "N/A" and 
            isinstance(content, str) and
            "No " not in content[:20] and
            "not available" not in content.lower() and
            len(content.strip()) > 30):
            filtered[section] = content
    
    return filtered


def create_consolidated_content(data_dict: Dict) -> str:
    """Create consolidated content string for LLM"""
    consolidated = ""
    for section, content in data_dict.items():
        consolidated += f"\n\n**{section}:**\n{content}\n"
    return consolidated


def create_comprehensive_package(nct_id: str, raw_data: Dict, processed_data: Dict, 
                                 summary: str, messages: List) -> Dict:
    """Create comprehensive data package for download"""
    return {
        "metadata": {
            "nct_id": nct_id,
            "export_date": "2025-10-16",
            "api_version": "ClinicalTrials.gov API v2",
            "processing_model": "GPT-4o",
            "app_version": "1.0-langgraph"
        },
        "raw_api_response": raw_data,
        "processed_extraction": processed_data,
        "ai_generated_summary": summary,
        "conversation_history": messages
    }
