"""
Generate PDF report from markdown PROJECT_REPORT.md
Uses reportlab for professional PDF generation
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import os
import re
from datetime import datetime

class NumberedCanvas(canvas.Canvas):
    """Custom canvas for page numbering"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """Add page numbers to all pages"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        """Draw page number at the bottom of the page"""
        self.setFont("Helvetica", 9)
        self.setFillColorRGB(0.5, 0.5, 0.5)
        self.drawRightString(
            7.5 * inch, 0.5 * inch,
            f"Page {self._pageNumber} of {page_count}"
        )


def parse_markdown_to_pdf(md_file_path, output_pdf_path):
    """Parse markdown and generate professional PDF report"""
    
    # Read markdown file
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    h1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=16,
        fontName='Helvetica-Bold'
    )
    
    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#555555'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    h4_style = ParagraphStyle(
        'CustomH4',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=6,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        alignment=TA_JUSTIFY,
        fontName='Helvetica'
    )
    
    code_style = ParagraphStyle(
        'CustomCode',
        parent=styles['Code'],
        fontSize=8,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Courier',
        backColor=colors.HexColor('#f5f5f5'),
        borderPadding=5
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=4,
        leftIndent=20,
        fontName='Helvetica'
    )
    
    # Story to hold PDF elements
    story = []
    
    # Parse markdown content
    lines = content.split('\n')
    i = 0
    in_code_block = False
    code_block_lines = []
    code_block_type = None
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Handle code blocks
        if line.startswith('```'):
            if not in_code_block:
                # Start code block
                in_code_block = True
                code_block_type = line[3:].strip() if len(line) > 3 else 'text'
                code_block_lines = []
            else:
                # End code block
                in_code_block = False
                if code_block_lines:
                    code_text = '\n'.join(code_block_lines)
                    # Limit code block width
                    if len(code_text) > 3000:
                        code_text = code_text[:3000] + '\n... (truncated)'
                    pre = Preformatted(code_text, code_style)
                    story.append(pre)
                    story.append(Spacer(1, 10))
                code_block_lines = []
            i += 1
            continue
        
        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue
        
        # Skip empty lines
        if not line.strip():
            story.append(Spacer(1, 6))
            i += 1
            continue
        
        # Handle horizontal rules
        if line.strip() == '---':
            story.append(Spacer(1, 10))
            story.append(Table([[''], ['']], colWidths=[7*inch], style=[
                ('LINEABOVE', (0, 1), (-1, 1), 1, colors.grey)
            ]))
            story.append(Spacer(1, 10))
            i += 1
            continue
        
        # Handle headers
        if line.startswith('# '):
            text = line[2:].strip()
            if i == 0:  # Title
                story.append(Paragraph(text, title_style))
                story.append(Spacer(1, 20))
            else:
                story.append(Paragraph(text, h1_style))
            i += 1
            continue
        
        if line.startswith('## '):
            text = line[3:].strip()
            story.append(Paragraph(text, h2_style))
            i += 1
            continue
        
        if line.startswith('### '):
            text = line[4:].strip()
            story.append(Paragraph(text, h3_style))
            i += 1
            continue
        
        if line.startswith('#### '):
            text = line[5:].strip()
            story.append(Paragraph(text, h4_style))
            i += 1
            continue
        
        # Handle bullet points
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            text = line.strip()[2:].strip()
            # Convert markdown bold and inline code
            text = convert_markdown_inline(text)
            story.append(Paragraph(f'• {text}', bullet_style))
            i += 1
            continue
        
        # Handle numbered lists
        if re.match(r'^\d+\.\s+', line.strip()):
            text = re.sub(r'^\d+\.\s+', '', line.strip())
            text = convert_markdown_inline(text)
            story.append(Paragraph(text, bullet_style))
            i += 1
            continue
        
        # Handle bold metadata lines (e.g., **Project Name:** ...)
        if line.startswith('**') and ':**' in line:
            text = convert_markdown_inline(line)
            story.append(Paragraph(text, body_style))
            i += 1
            continue
        
        # Regular paragraph
        if line.strip():
            text = convert_markdown_inline(line)
            story.append(Paragraph(text, body_style))
        
        i += 1
    
    # Build PDF with numbered pages
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ PDF report generated: {output_pdf_path}")


def convert_markdown_inline(text):
    """Convert markdown inline formatting to HTML for reportlab"""
    # Process inline code FIRST before any other conversions (to avoid conflicts)
    # Temporarily replace code blocks with placeholders
    code_replacements = []
    code_pattern = r'`([^`]+)`'
    
    def replace_code(match):
        code_text = match.group(1)
        # Escape the code content
        code_text = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        placeholder = f"___CODE_{len(code_replacements)}___"
        code_replacements.append(f'<font name="Courier" color="#c7254e">{code_text}</font>')
        return placeholder
    
    text = re.sub(code_pattern, replace_code, text)
    
    # Now escape special XML characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Bold: **text** (process before italic to avoid conflicts)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
    
    # Italic: *text* or _text_
    text = re.sub(r'\*([^\*]+)\*', r'<i>\1</i>', text)
    text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
    
    # Links: [text](url) - just show text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'<i>\1</i>', text)
    
    # Restore code placeholders
    for i, code_html in enumerate(code_replacements):
        text = text.replace(f"___CODE_{i}___", code_html)
    
    return text


if __name__ == "__main__":
    # File paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    md_file = os.path.join(project_root, "reports", "PROJECT_REPORT.md")
    pdf_file = os.path.join(project_root, "reports", "PROJECT_REPORT.pdf")
    
    # Check if markdown file exists
    if not os.path.exists(md_file):
        print(f"❌ Markdown file not found: {md_file}")
        exit(1)
    
    print(f"📄 Reading markdown file: {md_file}")
    print(f"📝 Generating PDF report...")
    
    try:
        parse_markdown_to_pdf(md_file, pdf_file)
        print(f"\n✅ SUCCESS: PDF report created at:")
        print(f"   {pdf_file}")
        print(f"\n📊 File size: {os.path.getsize(pdf_file) / 1024:.1f} KB")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to generate PDF")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
