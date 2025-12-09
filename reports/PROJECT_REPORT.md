# Clinical Trial Analysis System - Technical Architecture Report

**Project Name:** GenAI Clinical Trials Analysis System  
**Date:** December 8, 2025  
**Version:** 2.0  
**Repository:** genai_clinicaltrials (ui_enhancements branch)

---

## Executive Summary

ClinicalIQ is an intelligent clinical trial analysis platform that automates document processing and enables semantic search across clinical trial databases. Built with Streamlit and LangGraph, the system extracts structured information from clinical trial protocols and provides conversational access to comparative trial data.

**Core Capabilities:**
- Automated extraction of 9 standardized clinical trial fields from PDFs and ClinicalTrials.gov URLs
- Quality-based routing: parser-only extraction for high-quality sources, GPT-4o-mini fallback for complex documents
- Human-in-the-loop refinement with field-level approval and re-extraction
- Natural language summarization of extracted trials (<400 words, markdown formatted)
- Interactive Q&A on extracted content: users ask questions about specific fields, system provides contextual answers from parsed data
- Retrieval Augemented Generation(RAG) semantic search across clinical trials database using ChromaDB
- Conversational interface with streaming responses and chat history persistence (SQLite)

## Technology Stack

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

**Environment Variables:**
- `OPENAI_API_KEY`: Required for GPT-4o-mini and embeddings
- `CHROMA_DB_PATH`: Vector database location (default: ./db/clinical_trials_vectordb)
- `STREAMLIT_SERVER_PORT`: Web interface port (default: 8501)
- `MAX_UPLOAD_SIZE`: Maximum PDF file size (default: 200MB)

---

## Project Structure

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
### How the System Works

**Phase 1: Document Processing, Extraction & Summarization**
Users provide either a PDF clinical trial protocol or a ClinicalTrials.gov URL (with NCT identifier). The system routes to the appropriate extraction method:
- **URL input:** Fetches structured JSON from ClinicalTrials.gov API v2
- **PDF input:** Uses EnhancedClinicalTrialParser with multi-method extraction (pdfplumber → PyPDF2 → pdfminer.six)

After extraction, the system calculates confidence and completeness scores. If scores fall below thresholds (confidence < 0.5 OR completeness < 0.6), the workflow automatically triggers GPT-4o-mini for intelligent re-extraction using the MultiTurnExtractor.

Once extraction completes, the `chat_node` generates a natural language summary of the clinical trial using GPT-4o-mini with the SYSTEM_MESSAGE prompt (400-word limit, markdown formatting). Users can then ask follow-up questions about the extracted content (e.g., "What are the inclusion criteria?" or "Summarize the adverse events"), and the system streams contextual responses based on the parsed_json data.

**Phase 2: Retrieval Augmented Generation (RAG) Powered Search**
Users can query the clinical trials database conversationally (e.g., "Find similar HIV treatment studies"). The system:
1. Generates query embeddings using OpenAI's text-embedding-ada-002
2. Performs vector similarity search in ChromaDB (cosine similarity, threshold > 0.3)
3. Retrieves top 5 relevant trials with metadata filtering
4. Generates contextual responses using GPT-4o-mini with retrieved trial summaries

**User Interface Features**

The Streamlit web app (UI/app.py) provides:
- **File/URL Input:** PDF upload (max 200MB) with validation, or URL input with automatic NCT ID extraction
- **Chat Interface:** Streaming responses using `chat_node_stream()` with token-by-token display and cursor indicator
- **Session Management:** SQLite database stores conversations, extraction states, and uploaded file metadata across sessions
- **Extraction Results:** Tabbed interface showing metrics (confidence, completeness, field counts) and JSON viewer with expandable fields
- **Human-in-the-Loop:** Field-level approval/refinement buttons trigger targeted re-extraction via MultiTurnExtractor
- **Export Options:** Download extracted data as JSON or generate PDF summaries with embedded metadata
- **Performance Caching:** `@st.cache_resource` for workflow initialization, `@st.cache_data(ttl=60)` for database queries

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
│  ║         PHASE 2: RAG POWERED SEARCH & ANALYSIS            ║  │
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

**Step 1: Input Classification** (`classify_input` node)
- Detects NCT IDs (regex: `NCT\d{8}`) → classifies as URL
- Detects .pdf extension or 'pdf' in path → classifies as PDF
- Empty input with chat query → classifies as RAG-only or followup

**Step 2: Primary Extraction** (conditional routing)
- **URL path:** `extract_from_url` node fetches JSON from ClinicalTrials.gov API v2, maps response to 9-field schema
- **PDF path:** `parse_pdf` node instantiates EnhancedClinicalTrialParser, tries pdfplumber (primary) → PyPDF2 (fallback) → pdfminer.six (last resort). Uses regex patterns to identify clinical trial sections and extract content with page references.

**Step 3: Quality Evaluation** (`check_quality` node)
- Calculates confidence score (0.0-1.0) based on extraction method, content length, structured elements presence
- Calculates completeness score as percentage of 9 fields with >30 chars and non-placeholder text
- Routes to LLM fallback if confidence < 0.5 OR completeness < 0.6

**Step 4: LLM Fallback** (conditional, `llm_multi_turn_fallback` node)
- Uses MultiTurnExtractor to process document field-by-field with GPT-4o-mini
- Each field extracted independently with targeted prompts, avoiding rate limits
- Returns structured JSON validated against schemas, updates `parsed_json` and sets `used_llm_fallback = True`

**Step 5: Summary Generation & Interactive Q&A** (`chat_node`)
- **Initial Summary:** Formats extracted `parsed_json` into natural language using GPT-4o-mini with SYSTEM_MESSAGE prompt ("clinical research summarization expert", <400 words, markdown formatting)
- **Citation Integration:** Includes page numbers, confidence/completeness scores, extraction method, NCT ID
- **Streaming Output:** Token-by-token display with cursor indicator ("▌")
- **Follow-up Questions:** Users can query specific fields ("What are the eligibility criteria?") or request refinements
  - System classifies query intent: extraction (current document) vs. search (database RAG)
  - Extracts relevant fields from `parsed_json` or `data_to_summarize`
  - Generates contextual responses with GPT-4o-mini streaming
  - Maintains conversation history in SQLite for context awareness
- **Field Refinement:** Users can approve/request re-extraction of specific fields via UI buttons, triggering targeted MultiTurnExtractor calls

#### 1.2.2 Phase 2: Retrieval Augmented Generation (RAG) Powered Search

**Step 1: Query Classification** (`should_use_rag_tool` function)
- Detects search intent via keywords: "similar", "compare", "find studies", drug names, conditions
- Routes to RAG if detected, otherwise treats as document-specific question

**Step 2: Query Enhancement**
- Extracts context from current study: condition, intervention, phase
- Appends to query: "[Context: HIV, Dolutegravir, Phase III]"

**Step 3: Vector Search** (ChromaDB)
- Generates query embedding (1536-dim) via text-embedding-ada-002
- Computes cosine similarity against stored trial vectors
- Filters results with similarity > 0.3
- Returns top 5 trials with metadata

**Step 4: Response Generation** (`chat_node` with RAG results)
- Constructs prompt with: user query + current study summary + top 3 retrieved trials
- GPT-4o-mini generates comparative response with NCT ID citations
- Streams response token-by-token to UI

### 1.3 Component Architecture
- **Framework:** LangGraph 0.6.10 with StateGraph and conditional routing
- **State:** TypedDict `WorkflowState` with 20+ fields including `parsed_json`, `confidence_score`, `used_llm_fallback`, `rag_tool_results`
- **LLM:** ChatOpenAI with gpt-4o-mini (streaming and non-streaming instances)
- **Nodes:**
  - `classify_input`: Detects PDF/URL/RAG-only via regex and path analysis
  - `parse_pdf`: EnhancedClinicalTrialParser with multi-method fallback
  - `extract_from_url`: ClinicalTrials.gov API v2 fetcher
  - `check_quality`: Calculates confidence/completeness, routes to LLM if needed
  - `llm_multi_turn_fallback`: MultiTurnExtractor for field-by-field extraction
  - `chat_node`: Generates summaries, handles follow-up Q&A on extracted content, RAG integration, streaming responses
- **Routing:** Conditional edges based on input_type and quality thresholds
- **Query Classification:** `should_use_rag_tool()` distinguishes document-specific questions from database searches

#### 1.3.2 PDF Parser (enhanced_parser.py)
- **Multi-method extraction:** pdfplumber (primary) → PyPDF2 (fallback) → pdfminer.six (last resort)
- **Section detection:** Regex patterns for clinical trial headers ("Objectives", "Inclusion Criteria", etc.)
- **Table extraction:** pdfplumber's layout analysis for structured data
- **Output:** ClinicalTrialData object with 9 fields + page_references dict
- **Optional features:** OCR (Tesseract) and NLP (spaCy) disabled by default for performance

#### 1.3.3 Data Schema & Standards

**9-Field Standardized Structure:**

1. **study_overview**: Title, NCT ID, phase, condition, study type, design
2. **brief_description**: 2-4 paragraph summary of purpose, background, rationale
3. **primary_secondary_objectives**: Primary/secondary endpoints with measurement timepoints
4. **treatment_arms_interventions**: Arm names, sample sizes, drug details (name, dosage, route, duration)
5. **eligibility_criteria**: Inclusion/exclusion criteria, medical requirements
6. **enrollment_participant_flow**: Target/actual enrollment, participant disposition, demographics
7. **adverse_events_profile**: Common/serious AEs with incidence rates, grade 3/4 labs, discontinuations
8. **study_locations**: Countries, site counts, principal investigators, coordinating centers
9. **sponsor_information**: Primary sponsor, collaborators, CROs, funding sources

**Enhanced Data Structure with Metadata:**

Each field is stored as a JSON object with metadata enabling quality tracking and source attribution:

```json
{
  "content": "Detailed text content",
  "page_numbers": [5, 6, 7],
  "confidence_score": 0.85,
  "extraction_method": "multi_turn_llm",
  "last_updated": "2025-12-08T14:32:00Z",
  "word_count": 247
}
```

- **Citation tracking:** `page_numbers` array records PDF pages containing the information
- **Quality assessment:** `confidence_score` (0.0-1.0) indicates extraction reliability
- **Provenance:** `extraction_method` (api/pdfplumber/pypdf2/multi_turn_llm) shows data source
- **Update management:** `last_updated` timestamp tracks refinements
- **Completeness:** `word_count` measures content richness (threshold: 30 chars)

### 1.4 Quality Metrics & Intelligent Routing

**Confidence Score:** Weighted metric (0.0-1.0) based on extraction method (40%), content length (30%), structured elements (20%), and citation availability (10%). Threshold: 0.5.

**Completeness Score:** Percentage of 9 fields with >30 chars and non-placeholder text. Threshold: 0.6.

**Multi-Turn Refinement:** Users can request field-specific re-extraction via UI buttons, triggering targeted MultiTurnExtractor calls with feedback context.

**RAG Quality Metrics:**
- **Semantic Similarity:** Cosine similarity scores (0.0-1.0) with threshold > 0.3
- **Context Relevance:** Secondary LLM validation of retrieved content relevance
- **Citation Accuracy:** NCT ID verification and similarity score reporting

**Intelligent Routing Logic:**

The system routes between Phase 1 (extraction) and Phase 2 (RAG search) based on input type and user intent. Within Phase 1, quality thresholds (confidence ≥ 0.5 AND completeness ≥ 0.6) determine whether LLM fallback is needed. If thresholds are met, the system proceeds to summary generation; otherwise, MultiTurnExtractor performs intelligent re-extraction.

---

## 2. Quality Metrics Calculation

### 2.1 Phase 1: Extraction Quality Metrics

#### 2.1.1 Confidence Score Calculation
The confidence score evaluates the quality and reliability of extracted content through a weighted formula:

**Calculation Formula:**
```
Confidence = (Method_Score × 0.4) + (Content_Score × 0.3) + (Structure_Score × 0.2) + (Citation_Score × 0.1)
```

**Component Breakdown:**

1. **Method Score (Weight: 40%)**
   - Multi-turn LLM extraction: 1.0 (most reliable, understands context)
   - ClinicalTrials.gov API: 0.9 (structured source, high accuracy)
   - Clean PDF parse with pdfplumber: 0.7 (good quality but may miss nuances)
   - Fallback PyPDF2 extraction: 0.5 (basic text, may have formatting issues)
   - Degraded pdfminer extraction: 0.3 (poor quality, many errors likely)

2. **Content Score (Weight: 30%)**
   - Based on character count:
     - >500 characters: 1.0 (comprehensive detail)
     - 200-500 characters: 0.7 (adequate information)
     - 50-200 characters: 0.4 (minimal information)
     - <50 characters: 0.1 (insufficient data)
   - Adjusted down if content contains placeholder phrases like "not specified", "N/A", "to be determined"

3. **Structure Score (Weight: 20%)**
   - Presence of structured elements increases score:
     - Contains numbered/bulleted lists: +0.3
     - Contains specific numeric data (doses, counts, percentages): +0.3
     - Contains tables or tabular data: +0.2
     - Contains section headers or clear organization: +0.2
   - Maximum: 1.0, Minimum: 0.0 (unstructured prose only)

4. **Citation Score (Weight: 10%)**
   - Has specific page number references: 1.0
   - Has section references but no page numbers: 0.5
   - No citations available: 0.0

**Example Calculation:**

Field: "treatment_arms_interventions" extracted from PDF
- Method: pdfplumber (clean parse) → Method_Score = 0.7
- Content: 420 characters with detailed dosing → Content_Score = 0.7
- Structure: Contains numbered list and dosages → Structure_Score = 0.6
- Citation: Pages 12-14 referenced → Citation_Score = 1.0

Confidence = (0.7 × 0.4) + (0.7 × 0.3) + (0.6 × 0.2) + (1.0 × 0.1) = 0.28 + 0.21 + 0.12 + 0.10 = **0.71**

This score of 0.71 is above the 0.5 threshold, so no LLM fallback is triggered for this field.

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

**Cosine Similarity Formula:**
```
cosine_similarity = (A · B) / (||A|| × ||B||)
```
Where A · B is the dot product and ||A||, ||B|| are vector magnitudes.

**Threshold Filtering:**
- Similarity ≥ 0.7: Highly relevant
- Similarity 0.5-0.7: Moderately relevant
- Similarity 0.3-0.5: Weakly relevant
- Similarity < 0.3: Not relevant (filtered out)

#### 2.2.2 Context Relevance Scoring
LLM-based relevance evaluation ensures retrieved contexts directly address user queries:
- **Secondary validation**: Uses LLM to evaluate how well retrieved content answers the specific query
- **Relevance scale**: 0.0 (completely irrelevant) to 1.0 (highly relevant)
- **Quality control**: Supplements vector similarity with semantic understanding
- **Fallback handling**: Defaults to moderate relevance (0.5) if scoring fails

This dual-layer approach (vector + LLM) improves response accuracy and user satisfaction.

---

## 3. RAG Query Formation and Processing

### 3.1 Query Classification & Enhancement

**Intent Detection:** System classifies queries as extraction (document-specific), search (database RAG), or hybrid based on keywords and patterns.

**Query Enhancement:** Automatically appends context from current study (condition, intervention, phase) to improve RAG retrieval accuracy.

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

### 4.1 ChromaDB Vector Database

**Storage:** Persistent SQLite backend at `./db/clinical_trials_vectordb/` with ACID compliance

**Embeddings:** OpenAI text-embedding-ada-002 (1536-dim vectors) automatically generated on document insertion

**Metadata Schema:**
- **Identifiers:** NCT ID, study title, short title
- **Classification:** Phase, study type, intervention model, therapeutic area
- **Medical Context:** Condition, interventions, MeSH terms, outcomes
- **Administrative:** Sponsors, collaborators, regulatory info
- **Timeline:** Start/completion dates, enrollment periods
- **Geography:** Countries, facility locations
- **Technical:** Confidence scores, page numbers, extraction methods

**Query Capabilities:**
- Metadata filtering before vector similarity computation
- Multiple filter types: exact match, multiple values, numerical ranges, text patterns
- Complex boolean logic (AND/OR combinations)

### 4.2 Document Ingestion & Maintenance

**Ingestion Pipeline:**
1. **Chunking:** Split by 9-field sections with page attribution
2. **Embedding:** Auto-generated via text-embedding-ada-002
3. **Validation:** Check confidence (>0.4), completeness (≥3 fields), NCT ID
4. **Storage:** Batch inserts (50 docs) with retry logic (3 attempts, exponential backoff)

**Parallel Processing:** ThreadPoolExecutor (4 threads) for concurrent document processing

**Maintenance:**
- **Deduplication:** SHA-256 content hash matching
- **Embedding Updates:** Regenerate vectors when model changes
- **Optimization:** Monthly index rebuilds and SQLite compaction (20-30% speed improvement)

---

## 5. Conclusion

ClinicalIQ provides an end-to-end solution for clinical trial document analysis, combining intelligent extraction with semantic search capabilities:

**Core Features:**
- **Adaptive extraction:** Quality-based routing between parser-only and GPT-4o-mini fallback
- **Human-in-the-loop:** Field-level approval and refinement via MultiTurnExtractor
- **Semantic search:** ChromaDB vector database with cosine similarity (threshold > 0.3)
- **Conversational UI:** Streamlit with streaming responses and SQLite persistence
- **Production-ready:** Modular architecture, comprehensive error handling, caching optimizations

The system is deployed on the `ui_enhancements` branch with full database integration, RAG tool support, and human feedback loops for quality assurance.

---

**Report Generated:** December 8, 2025  
**Version:** 2.0 - Technical Architecture Documentation  
**Contact:** Clinical Trial Analysis System Team  
**Repository:** https://github.com/SowmyaPodila6/genai_clinicaltrials (ui_enhancements branch)
