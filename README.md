# Clinical Trial Analysis System (ClinicalIQ)

A comprehensive AI-powered system for clinical trial document analysis with intelligent extraction, re-extraction capabilities, and semantic search.

## 🚀 Quick Setup

### Prerequisites
- **Python 3.11+** , (It does not work with Pyton 3.14. Dated 2025-12-18. I am using 3.13.)
- **OpenAI API Key** (required)

### 1. Clone & Install
```bash
git clone https://github.com/SowmyaPodila6/genai_clinicaltrials.git
cd genai_clinicaltrials
git checkout ui_enhancements

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set API Key
```bash
# Windows PowerShell:
setx OPENAI_API_KEY "your-api-key-here"

# macOS/Linux/WSL:
export OPENAI_API_KEY="your-api-key-here"

# Or create .env file:
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

### 3. Run Application
```bash
streamlit run UI/app.py
```
**→ Open http://localhost:8501**

## 📁 Repository Structure

```
genai_clinicaltrials/
├── 📱 UI/
│   └── app.py                      # Streamlit web interface
├── 🔄 langgraph_custom/
│   ├── langgraph_workflow.py       # Main workflow orchestration  
│   ├── multi_turn_extractor.py     # Re-extraction with user feedback
│   ├── enhanced_parser.py          # PDF text extraction
│   ├── extraction_schemas.py       # Data validation schemas
│   ├── rag_tool.py                 # RAG search functionality
│   ├── vector_db_manager.py        # ChromaDB vector database
│   └── prompts.py                  # LLM prompt templates
├── 🧪 tests/                       # Test scripts
├── 💾 data/
│   └── chat_history.db             # SQLite conversation storage
├── 🗃️ db/
│   └── clinical_trials_vectordb/   # ChromaDB vector storage  
├── 📄 uploads/                     # Temporary PDF storage
├── 🛠️ utils/
│   ├── utils.py                    # Helper functions
│   └── generate_docx.py           # Document generation
├── 📋 reports/                     # Technical documentation
├── 📦 requirements.txt             # Python dependencies
├── 📝 pyproject.toml              # Poetry configuration (alternative)
└── ⚙️ debug_*.py                  # Debug and testing scripts
```

## 🎯 Core Features

### ✨ **Intelligent Extraction**
- **PDF Upload**: Drag & drop clinical trial protocols
- **URL Import**: Paste ClinicalTrials.gov links (NCT numbers)
- **9 Data Fields**: Study overview, objectives, arms, criteria, etc.
- **Quality Scoring**: Confidence & completeness metrics
- **LLM Fallback**: Enhanced extraction when quality is low

### 🔄 **Re-extraction with Feedback**
- **Field-level Refinement**: Click "Refine" on any extracted field
- **User Feedback**: Provide specific instructions for improvement
- **Real-time Updates**: See changes immediately in JSON view
- **Persistent Storage**: All changes saved to database

### 🔍 **RAG Search & Comparison**
- **Semantic Search**: Find similar studies using AI embeddings  
- **Comparative Analysis**: Side-by-side study comparisons
- **Query Examples**: "Find similar cancer immunotherapy trials"
- **Metadata Filtering**: Filter by phase, condition, sponsor

## 📖 How to Use

### 1. Upload & Extract
1. **Start app**: Run `streamlit run UI/app.py` 
2. **Upload**: Drag PDF file or paste ClinicalTrials.gov URL
3. **Wait**: System extracts 9 structured data fields automatically
4. **Review**: Check extraction quality scores and results

### 2. Review & Refine 
1. **View JSON**: Switch to "View JSON" tab to see all fields
2. **Refine Fields**: Click "Refine" button on any field needing improvement
3. **Provide Feedback**: Enter specific instructions (e.g., "Add more dosing details")
4. **See Updates**: Refined content appears immediately

### 3. Search & Compare
1. **Ask Questions**: Use chat to search for similar studies
2. **Get Analysis**: Request comparative analysis or insights
3. **Explore Database**: Search across all processed clinical trials
- "Find similar studies using DTG + TAF + FTC"
- "Compare this study to other Phase III oncology trials"
- "What are the typical adverse events for this drug combination?"
- "Search for studies with similar inclusion criteria"
```

#### Database Search with Filters
```python
# Programmatic search example:
from langgraph_custom.rag_tool import search_similar_clinical_trials

results = search_similar_clinical_trials(
    query="immunotherapy cancer treatment",
    filters={
        "phase": "Phase III",
        "condition": "Advanced Cancer",
        "enrollment": {"$gte": 300}
    },
    top_k=5
)
```

## ⚙️ Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM services | None | ✅ |
| `CHROMA_DB_PATH` | Path to ChromaDB storage | `./db/clinical_trials_vectordb` | ❌ |
| `STREAMLIT_SERVER_PORT` | Streamlit server port | `8501` | ❌ |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | ❌ |
| `MAX_UPLOAD_SIZE` | Maximum PDF upload size (MB) | `200` | ❌ |

### Quality Thresholds

```python
# Modify these in langgraph_custom/multi_turn_extractor.py
CONFIDENCE_THRESHOLD = 0.5      # Trigger LLM fallback if below
COMPLETENESS_THRESHOLD = 0.6    # Trigger LLM fallback if below
MIN_FIELD_LENGTH = 30           # Minimum characters for meaningful content
```

### Vector Database Settings

```python
# Modify these in langgraph_custom/vector_db_manager.py
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI embedding model
CHUNK_SIZE = 1500                           # Text chunk size for embeddings
CHUNK_OVERLAP = 150                         # Overlap between chunks
SIMILARITY_THRESHOLD = 0.3                  # Minimum similarity for results
```

## 🧪 Testing and Validation

### Running Tests

```bash
# Test the complete system
python test_workflow_rag.py

# Test re-extraction and summary features
python test_reextract_summary.py

# Test RAG integration
python test_rag_integration.py

# Test PDF extraction validation
python test_pdf_extraction_validation.py
```

### Test Data

Place test PDFs in the root directory or provide ClinicalTrials.gov URLs:
- NCT format: `https://clinicaltrials.gov/study/NCT01234567`
- API format: `https://clinicaltrials.gov/api/v2/studies/NCT01234567`

## 🔍 Troubleshooting

### Common Issues

#### 1. OpenAI API Key Issues
```bash
# Verify API key is set
echo $OPENAI_API_KEY  # Linux/macOS
echo %OPENAI_API_KEY%  # Windows

## ⚙️ Configuration

### Environment Variables (Optional)
```bash
# Create .env file for custom settings:
OPENAI_API_KEY=your_api_key_here
CHROMA_DB_PATH=./db/clinical_trials_vectordb  
STREAMLIT_SERVER_PORT=8501
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=200
```

## 🧪 Testing

### Quick Tests
```bash
# Test shared LLM and re-extraction
python test_shared_llm_reextraction.py

# Test complete pipeline  
python double_check_reextraction.py

# Debug database state
python debug_state.py
```

### Example URLs for Testing
- `https://clinicaltrials.gov/study/NCT02419716`
- `https://clinicaltrials.gov/study/NCT03682978`

## 🔧 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| ❌ "OPENAI_API_KEY not found" | Set environment variable: `$env:OPENAI_API_KEY="your-key"` |
| ❌ "Port 8501 already in use" | Use different port: `streamlit run UI/app.py --server.port 8502` |
| ❌ PDF upload fails | Ensure PDF is text-based (not scanned image) |
| ❌ Re-extraction not working | Check that API key is set correctly |
| ❌ Database errors | Delete `data/chat_history.db` to reset |

### Debug Mode
```bash
# Enable detailed logging
$env:LOG_LEVEL="DEBUG"
streamlit run UI/app.py
```

## 📊 Technical Details

### Data Schema (9 Extracted Fields)
1. **Study Overview** - Title, NCT ID, phase, disease, study type
2. **Brief Description** - Study summary and background  
3. **Primary & Secondary Objectives** - Endpoints and outcome measures
4. **Treatment Arms & Interventions** - Arms, drugs, doses, schedules
5. **Eligibility Criteria** - Inclusion/exclusion criteria
6. **Enrollment & Participant Flow** - Patient numbers and disposition
7. **Adverse Events Profile** - Safety data and AE tables
8. **Study Locations** - Sites, countries, investigators  
9. **Sponsor Information** - Sponsor, collaborators, CRO

### Quality Metrics
- **Confidence Score**: Content richness (0.0-1.0)
- **Completeness Score**: Field coverage percentage (0.0-1.0)
- **LLM Fallback**: Triggered when confidence <0.5 OR completeness <0.6

### RAG Search Capabilities
- **Vector Database**: ChromaDB for semantic similarity search
- **Query Types**: Similar studies, comparative analysis, drug mechanisms
- **Metadata Filtering**: Phase, condition, sponsor, enrollment size

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies (if available)
pip install -r requirements_dev.txt

# Run tests before submitting changes
python double_check_reextraction.py
```

### Code Standards
- Follow PEP 8 for Python code style
- Use type hints and docstrings
- Test new features with provided scripts
- Update README for new functionality

## 📞 Support

### Getting Help
1. **Check troubleshooting** section above
2. **Review logs** with debug mode enabled  
3. **Test components** using provided debug scripts
4. **Search issues** in GitHub repository

### System Requirements
- **Minimum**: Python 3.8+, 4GB RAM, 2GB disk space
- **Recommended**: Python 3.11+, 8GB RAM, 10GB disk space  
- **Network**: Internet required for OpenAI API

---

## 📄 Documentation

**Technical Architecture**: See `reports/PROJECT_REPORT.md` for detailed system design

**Version**: 2.0 (December 2025) - Re-extraction & RAG integration

**License**: Refer to repository license for usage terms
