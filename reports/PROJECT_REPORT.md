# Clinical Trial Analysis System - Technical Architecture Report

**Project Name:** GenAI Clinical Trials Analysis System  
**Date:** December 8, 2025  
**Version:** 2.0  
**Repository:** genai_clinicaltrials (ui_enhancements branch)

---

## Executive Summary

This project implements an intelligent two-phase clinical trial document analysis system using LangGraph workflows and GPT-4o. The system combines automated extraction and summarization (Phase 1) with semantic search and retrieval-augmented generation (Phase 2). It processes clinical trial data from ClinicalTrials.gov URLs and PDF protocols, providing comprehensive analysis and comparative insights through an interactive chat interface.

**Key Technical Features:**
- **Two-phase architecture:** Extraction/Summarization (Phase 1) + RAG Search (Phase 2)
- **Dual-source support:** ClinicalTrials.gov API and PDF documents with intelligent quality routing
- **Multi-turn extraction:** Field-by-field extraction with user feedback and re-extraction capabilities
- **Vector-based RAG:** ChromaDB integration for semantic search across clinical trials database
- **9-field standardized schema:** Comprehensive clinical trial data structure with citation support
- **Interactive UI:** ClinicalIQ-branded Streamlit interface with conversation history and streaming responses

---

## 1. Architecture Design

### 1.1 Two-Phase System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ClinicalIQ - Web Interface                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ File Upload │  │ URL Input   │  │ Chat        │  │ History     │  │
│  │ (PDF Files) │  │ (CT.gov)    │  │ Interface   │  │ (SQLite)    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph Workflow Engine                     │
│                                                                 │
│  ╔═════════════════════════════════════════════════════════════╗  │
│  ║                    PHASE 1: EXTRACTION                     ║  │
│  ╠═════════════════════════════════════════════════════════════╣  │
│  ║                                                             ║  │
│  ║  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ║  │
│  ║  │   Input     │───▶│   Route     │───▶│  Quality    │    ║  │
│  ║  │ Classifier  │    │  (PDF/URL)  │    │  Router     │    ║  │
│  ║  └─────────────┘    └─────────────┘    └─────────────┘    ║  │
│  ║         │                   │                   │         ║  │
│  ║         └─────────┬─────────┘                   │         ║  │
│  ║                   ▼                             ▼         ║  │
│  ║  ┌─────────────┐       ┌─────────────┐  ┌─────────────┐  ║  │
│  ║  │ PDF Parser  │       │ URL Extract │  │ Multi-Turn  │  ║  │
│  ║  │ (Enhanced)  │       │ (CT.gov)    │  │ LLM Extract │  ║  │
│  ║  └─────────────┘       └─────────────┘  └─────────────┘  ║  │
│  ║         │                       │               │        ║  │
│  ║         └───────────────────────┼───────────────┘        ║  │
│  ║                                 ▼                        ║  │
│  ║                   ┌─────────────────────────┐            ║  │
│  ║                   │     Summary Generation  │            ║  │
│  ║                   │   (Structured Output)   │            ║  │
│  ║                   └─────────────────────────┘            ║  │
│  ╚═════════════════════════════════════════════════════════════╝  │
│                                │                               │
│                                ▼                               │
│  ╔═════════════════════════════════════════════════════════════╗  │
│  ║                    PHASE 2: RAG SEARCH                     ║  │
│  ╠═════════════════════════════════════════════════════════════╣  │
│  ║                                                             ║  │
│  ║  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ║  │
│  ║  │   Query     │───▶│   Vector    │───▶│  Enhanced   │    ║  │
│  ║  │ Classifier  │    │   Search    │    │  Response   │    ║  │
│  ║  └─────────────┘    └─────────────┘    └─────────────┘    ║  │
│  ║                            │                               ║  │
│  ║                            ▼                               ║  │
│  ║      ┌──────────────────────────────────────────┐         ║  │
│  ║      │         ChromaDB Vector Database         │         ║  │
│  ║      │     • Clinical trial protocols           │         ║  │
│  ║      │     • Semantic embeddings               │         ║  │
│  ║      │     • Metadata filtering                │         ║  │
│  ║      │     • Similarity search                 │         ║  │
│  ║      └──────────────────────────────────────────┘         ║  │
│  ╚═════════════════════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       External Services                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ OpenAI API  │  │ CT.gov API  │  │ ChromaDB    │  │ File Cache  │  │
│  │ GPT-4o-mini │  │ v2 Endpoint │  │ Vector DB   │  │ PDF Store   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Phase Architecture Details

#### 1.2.1 Phase 1: Extraction & Summarization
**Purpose:** Extract structured data from clinical trial documents and generate comprehensive summaries

**Key Components:**
- **Enhanced PDF Parser:** Multi-method extraction (pdfplumber, PyPDF2, pdfminer.six)
- **ClinicalTrials.gov API Integration:** Direct data fetching from structured sources
- **Multi-Turn Extractor:** Field-by-field extraction with user feedback loops
- **Quality-based Routing:** Confidence/completeness metrics determine LLM fallback
- **Re-extraction Capabilities:** Users can provide feedback to refine specific fields

**Data Flow:**
1. Input classification (PDF vs URL)
2. Primary extraction (parser vs API)
3. Quality evaluation (confidence + completeness scores)
4. LLM fallback if quality thresholds not met
5. Structured summary generation
6. User feedback and re-extraction loops

#### 1.2.2 Phase 2: RAG Search & Comparative Analysis
**Purpose:** Provide semantic search and comparative insights across clinical trials database

**Key Components:**
- **ChromaDB Vector Database:** Stores embeddings of clinical trial protocols
- **Semantic Search:** Natural language queries for finding similar studies
- **RAG Tool Integration:** Retrieval-Augmented Generation for enhanced responses
- **Comparative Analysis:** Side-by-side comparison of treatment approaches
- **Query Classification:** Intelligent routing between extraction and search modes

**Data Flow:**
1. Query analysis and intent classification
2. Vector similarity search in ChromaDB
3. Context retrieval and ranking
4. Enhanced response generation with retrieved context
5. Comparative insights and recommendations
  - Download options (JSON, TXT formats)
  - Performance optimizations with `@st.cache_resource` and `@st.cache_data`

#### 1.2.2 Workflow Engine (langgraph_workflow.py)
- **Framework:** LangGraph 0.6.10
- **State Management:** TypedDict-based WorkflowState
- **Nodes:**
  1. **classify_input:** Determines if input is PDF or URL
  2. **parse_pdf:** Extracts data using EnhancedClinicalTrialParser
  3. **extract_from_url:** Fetches data from ClinicalTrials.gov API
  4. **check_quality:** Evaluates extraction quality (conditional edge)
  5. **llm_fallback:** GPT-4o full document extraction with citations
  6. **chat_node:** Generates summaries and answers questions

#### 1.2.3 PDF Parser (enhanced_parser.py)
- **Multi-method extraction:**
  - pdfplumber (primary)
  - PyPDF2 (fallback)
  - pdfminer.six (deep extraction)
- **Section detection:** Pattern-based clinical trial section identification
- **Table extraction:** Structured data extraction
- **Optional features:** OCR (Tesseract), NLP (spaCy) - disabled for performance

#### 1.3.4 Data Schema & Standards
**9-Field Standardized Structure with Citations:**
1. `study_overview` - Title, NCT ID, phase, disease [Page refs]
2. `brief_description` - Study summary and background [Page refs]
3. `primary_secondary_objectives` - Endpoints and outcome measures [Page refs]
4. `treatment_arms_interventions` - Arms, drugs, doses, schedules [Page refs]
5. `eligibility_criteria` - Inclusion/exclusion criteria [Page refs]
6. `enrollment_participant_flow` - Patient numbers and disposition [Page refs]
7. `adverse_events_profile` - Safety data and AE tables [Page refs]
8. `study_locations` - Sites, countries, investigators [Page refs]
9. `sponsor_information` - Sponsor, collaborators, CRO [Page refs]

**Enhanced Data Structure:**
```json
{
  "content": "Extracted field content",
  "page_numbers": [1, 2, 3],
  "confidence_score": 0.85,
  "extraction_method": "multi_turn_llm"|"parser"|"api"
}
```

### 1.4 Quality Metrics & Routing

**Phase 1 Quality Assessment:**
- **Confidence Score:** Based on content richness and extraction method reliability
- **Completeness Score:** Percentage of 9 fields with meaningful data (>30 chars)
- **Citation Quality:** Availability and accuracy of page number references
- **Multi-Turn Capability:** Re-extraction with user feedback for quality improvement

**Phase 2 Retrieval Quality:**
- **Semantic Similarity:** Vector cosine similarity scores for retrieved documents
- **Context Relevance:** LLM-based relevance scoring of retrieved passages
- **Answer Completeness:** Coverage of user query across retrieved documents
- **Citation Accuracy:** Proper attribution of retrieved information sources

**Intelligent Routing Logic:**
- Phase 1 triggers when document extraction/summarization needed
- Phase 2 triggers when comparative analysis or similar study search requested
- Hybrid mode combines current document analysis with database search
- Quality thresholds determine LLM fallback vs parser-only extraction

---

## 2. Quality Metrics Calculation

### 2.1 Phase 1: Extraction Quality Metrics

#### 2.1.1 Confidence Score Calculation
The confidence score evaluates the quality and reliability of extracted content based on:
- **Content richness**: Longer, more detailed content receives higher scores
- **Extraction method reliability**: Multi-turn LLM extraction gets highest score, API second, parser baseline
- **Citation availability**: Content with page number references gets bonus points
- **Structured data presence**: Content containing numbers, lists, and structured elements scores higher

Final score ranges from 0.0 to 1.0, with scores below 0.5 triggering LLM fallback.

#### 2.1.2 Completeness Score Calculation
The completeness score measures how many of the 9 standard fields contain meaningful data:
- **Meaningful content**: Must have >30 characters and not be placeholder text ("N/A", "not available")
- **Domain validation**: Content must contain relevant clinical trial keywords
- **Field coverage**: Calculated as percentage of completed fields out of total 9 fields

Scores below 0.6 (less than 60% of fields completed) trigger LLM fallback for improved extraction.

#### 2.1.3 Quality-Based Routing Decision
The system automatically determines when to use expensive LLM fallback extraction based on quality thresholds:
- **Confidence threshold**: <0.5 indicates low-quality or unreliable content
- **Completeness threshold**: <0.6 means too many fields are empty or contain placeholders
- **Routing logic**: LLM fallback triggers if either threshold is not met

This ensures high-quality extraction while minimizing unnecessary API costs.

### 2.2 Phase 2: RAG Quality Metrics

#### 2.2.1 Vector Similarity Scoring
Vector similarity uses cosine similarity to measure semantic closeness between queries and documents:
- **Embedding comparison**: Compares query embeddings with document embeddings in vector space
- **Cosine similarity**: Measures angle between vectors, ranging from 0.0 (no similarity) to 1.0 (identical)
- **Normalization**: Ensures consistent scoring regardless of vector magnitude
- **Threshold filtering**: Results below 0.3 similarity are filtered out to maintain relevance

#### 2.2.2 Context Relevance Scoring
LLM-based relevance evaluation ensures retrieved contexts directly address user queries:
- **Secondary validation**: Uses LLM to evaluate how well retrieved content answers the specific query
- **Relevance scale**: 0.0 (completely irrelevant) to 1.0 (highly relevant)
- **Quality control**: Supplements vector similarity with semantic understanding
- **Fallback handling**: Defaults to moderate relevance (0.5) if scoring fails

This dual-layer approach (vector + LLM) improves response accuracy and user satisfaction.

---

## 3. RAG Query Formation and Processing

### 3.1 Query Classification

#### 3.1.1 Intent Detection
The system automatically classifies user queries to determine the appropriate processing approach:

**Query Categories:**
- **Extraction**: Document analysis and summarization requests ("extract", "summarize", "objectives")
- **Search**: Finding similar studies or comparative analysis ("similar studies", "compare", drug names)
- **Hybrid**: Current document analysis with comparative context (default for ambiguous queries)

**Classification Process:**
- Analyzes query text for specific keywords and patterns
- Scores each category based on indicator presence
- Routes to highest-scoring category or defaults to hybrid mode
- Enables intelligent switching between Phase 1 and Phase 2 operations

#### 3.1.2 Query Enhancement for RAG
Queries are automatically enhanced with context from the current study to improve retrieval accuracy:

**Context Extraction:**
- **Disease terms**: Primary condition and therapeutic area
- **Drug information**: Treatment names and intervention types
- **Study phase**: Clinical trial phase for appropriate comparisons
- **Patient population**: Demographics and eligibility criteria

**Enhancement Process:**
- Extracts relevant terms from current study overview and interventions
- Appends context terms to user query for better semantic matching
- Maintains original user intent while improving search precision
- Example: "side effects" becomes "side effects (context: HIV, DTG, Phase III)"

### 3.2 Vector Database Operations

#### 3.2.1 Database Schema and Structure
**ChromaDB Collection Configuration:**
- **Collection Name**: "clinical_trials_vectordb"
- **Embedding Model**: OpenAI text-embedding-ada-002
- **Storage**: Persistent local storage with SQLite backend

**Core Metadata Fields:**
- **Identifiers**: NCT ID, study title, short title
- **Classification**: Phase, study type, intervention model, therapeutic area
- **Medical Context**: Condition, interventions, MeSH terms
- **Administrative**: Sponsors, collaborators, regulatory information
- **Timeline**: Start/completion dates, enrollment periods
- **Geography**: Countries, facility locations
- **Outcomes**: Primary/secondary endpoints
- **Technical**: Document sections, page numbers, confidence scores

#### 3.2.2 Document Ingestion Pipeline
**Efficient Document Processing Workflow:**

**Step 1 - Document Chunking:**
- Splits documents by clinical trial sections (9 standard fields)
- Creates separate chunks for each meaningful section
- Maintains source attribution with page number references

**Step 2 - Embedding Generation:**
- Uses OpenAI text-embedding-ada-002 for vector representations
- Automatically handled by ChromaDB embedding function
- Optimized for semantic search of medical content

**Step 3 - Metadata Extraction:**
- Extracts study identifiers, classifications, and administrative data
- Validates required fields and data quality
- Adds technical metadata (timestamps, extraction methods)

**Step 4 - Database Storage:**
- Stores document chunks with embeddings and metadata
- Implements proper indexing for fast retrieval
- Includes error handling and rollback capabilities

### 3.3 Retrieval and Response Generation

#### 3.3.1 Similarity Search Implementation
**Semantic Search Process:**

**Query Processing:**
- Converts user queries to vector embeddings using OpenAI's model
- Applies optional metadata filters (phase, condition, sponsor, etc.)
- Retrieves top similar documents based on cosine similarity

**Result Filtering and Ranking:**
- Filters results below similarity threshold (0.3) to ensure relevance
- Ranks by similarity score and metadata relevance
- Includes document content, metadata, and confidence scores
- Returns configurable number of top results (default: 5)

**Advanced Filtering Options:**
- Study phase, condition, intervention type
- Date ranges, enrollment size, geographic location
- Sponsor type (industry, academic, government)
- Study status and completion status

#### 3.3.2 RAG Response Generation
**Enhanced Response Creation Process:**

**Context Preparation:**
- Summarizes top 3 most relevant retrieved studies
- Includes study identifiers, metadata, and key content excerpts
- Incorporates current study context when available for comparison
- Maintains source attribution and similarity scores

**Response Generation Strategy:**
- Direct answers to user queries using retrieved evidence
- Comparative analysis highlighting patterns and differences
- Specific study references with NCT IDs for verification
- Scientific accuracy with proper source citations

**Output Structure:**
- Clear, direct response to the original query
- Supporting evidence from similar studies
- Comparative insights and trend analysis
- Actionable recommendations when appropriate
- Proper attribution to source studies and documents

---

## 4. Database Architecture and Usage

### 4.1 ChromaDB Vector Database Design

**Core Configuration:**
- **Storage**: Persistent ChromaDB with SQLite backend at `./db/clinical_trials_vectordb/`
- **Embedding Model**: OpenAI text-embedding-ada-002
- **Collection**: "clinical_trials" with automatic creation and state persistence

**Metadata Structure:**
- **Study Identifiers**: NCT ID, titles, document references
- **Classifications**: Phase, study type, intervention model, therapeutic area
- **Medical Context**: Conditions, treatments, MeSH terms, outcomes
- **Administrative**: Sponsors, collaborators, regulatory details
- **Timeline**: Study dates, enrollment data, demographics
- **Technical**: Extraction methods, confidence scores, processing timestamps

**Query Capabilities:**
- **Filtering**: Phase, condition, sponsor, date ranges, enrollment size
- **Search Types**: Exact match, multiple values, numerical ranges, text patterns
- **Complex Logic**: AND/OR combinations for precise study targeting

### 4.2 Database Operations

**Document Ingestion:**
- **Parallel Processing**: Concurrent document processing with configurable thread pools
- **Batch Operations**: Efficient grouped database writes with error handling
- **Quality Validation**: Documents validated before insertion with retry logic

**Maintenance:**
- **Deduplication**: Content-based duplicate detection and cleanup
- **Embedding Updates**: Automatic re-generation when models change
- **Performance Optimization**: Regular maintenance runs and health monitoring

---

## 5. Technology Stack and Dependencies

### 5.1 Core Technologies

**Backend Framework:**
- Python 3.11.9
- LangGraph 0.6.10 (Workflow orchestration)
- LangChain 0.3.18 (LLM integration)
- ChromaDB 0.4.x (Vector database)

**Frontend:**
- Streamlit 1.50.0 (Web interface)
- Custom CSS for ClinicalIQ branding

**AI/ML Services:**
- OpenAI GPT-4o-mini (Text generation)
- OpenAI text-embedding-ada-002 (Vector embeddings)

**PDF Processing:**
- pdfplumber 0.11.4 (Primary PDF extraction)
- PyPDF2 3.0.1 (Fallback PDF processing)
- pdfminer.six 20231228 (Deep text extraction)

**Data Storage:**
- SQLite 3.x (Conversation history, session management)
- ChromaDB (Vector storage and similarity search)
- File system (PDF cache, temporary files)

### 5.2 Environment Configuration

**Required Environment Variables:**
- `OPENAI_API_KEY`: OpenAI API key for GPT-4o-mini and embeddings

**Optional Configuration:**
- `CHROMA_DB_PATH`: Vector database storage location (default: ./db/clinical_trials_vectordb)
- `STREAMLIT_SERVER_PORT`: Web interface port (default: 8501)
- `LOG_LEVEL`: Application logging level (default: INFO)
- `MAX_UPLOAD_SIZE`: Maximum PDF file size (default: 200MB)

### 5.3 File Structure Overview

```
genai_clinicaltrials/
├── UI/
│   └── app.py                      # Streamlit main application
├── langgraph_custom/
│   ├── __init__.py
│   ├── langgraph_workflow.py       # LangGraph workflow engine
│   ├── multi_turn_extractor.py     # Multi-turn extraction logic
│   ├── enhanced_parser.py          # PDF parsing with multi-method
│   ├── extraction_schemas.py       # Pydantic schemas for data validation
│   ├── prompts.py                  # LLM prompt templates
│   ├── rag_tool.py                 # RAG search implementation
│   └── vector_db_manager.py        # ChromaDB operations
├── db/
│   └── clinical_trials_vectordb/   # ChromaDB persistent storage
├── uploads/                        # Temporary PDF storage
├── utils/
│   └── utils.py                    # Utility functions
├── reports/                        # Project documentation
├── requirements.txt                # Python dependencies
├── .env                           # Environment configuration
└── README.md                      # Setup and usage guide
```

---

## 6. Conclusion

The Clinical Trial Analysis System Version 2.0 demonstrates a robust two-phase architecture that effectively combines document analysis with semantic search capabilities. The system's technical foundation provides:

**Phase 1 - Extraction & Summarization:**
- Intelligent quality-based routing with configurable thresholds
- Multi-turn extraction with user feedback loops
- Comprehensive citation tracking and validation
- Performance optimizations through caching and intelligent chunking

**Phase 2 - RAG Search & Analysis:**
- Advanced vector similarity search with metadata filtering
- Contextual query enhancement using current study information
- Sophisticated response generation with comparative analysis
- Scalable database architecture supporting large document collections

**Technical Strengths:**
- ✓ Modular, maintainable codebase with clear separation of concerns
- ✓ Comprehensive metrics calculation for quality assessment
- ✓ Advanced database operations with optimization strategies
- ✓ Flexible query processing with multiple intent classification
- ✓ Production-ready error handling and logging

This architecture provides a solid foundation for clinical trial document analysis while maintaining flexibility for future enhancements and scalability requirements.

---

**Report Generated:** December 8, 2025  
**Version:** 2.0 - Technical Architecture Documentation  
**Contact:** Clinical Trial Analysis System Team  
**Repository:** https://github.com/SowmyaPodila6/genai_clinicaltrials (ui_enhancements branch)
