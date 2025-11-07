# LangGraph Clinical Trial Workflow

A simple, clean LangGraph workflow for clinical trial document analysis following official LangGraph patterns.

## 🎯 Features

- **Automatic Input Classification**: Detects PDF vs URL inputs
- **Dual Parsing**:
  - PDF documents using enhanced parser
  - ClinicalTrials.gov URLs via API
- **Quality Assessment**:
  - Confidence scores (extraction quality)
  - Completeness scores (field coverage)
  - Missing field tracking
- **LLM Fallback**: Automatic fallback for low-confidence extractions
- **Interactive Chat**: Q&A on extracted data with full document access
- **Streamlit UI**: Clean interface with metrics visualization

## 📊 Workflow Graph

```
Start
  ↓
classify_input (determine PDF or URL)
  ↓
[Conditional: PDF or URL?]
  ↓                    ↓
pdf_parser      url_extractor
  ↓                    ↓
[Conditional: Quality check]
  ↓
[Low quality? → llm_fallback]
  ↓
chat_node (Q&A and summary)
  ↓
End
```

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements_langgraph.txt

# Set up environment variables
echo "OPENAI_API_KEY=your_key_here" > .env
```

### Run Tests

```bash
# Test workflow with visualization
python test_langgraph_workflow.py
```

This generates:
- `workflow_graph.png` - Visual graph representation
- `workflow_graph.mmd` - Mermaid diagram source
- `test_url_results.json` - URL test output
- `test_pdf_results.json` - PDF test output
- `test_chat_history.json` - Chat interaction log

### Run Streamlit App

```bash
streamlit run app_langgraph.py
```

## 📝 Usage Examples

### Basic Workflow Usage

```python
from langgraph_workflow import build_workflow

# Build workflow
app = build_workflow()

# Process URL
result = app.invoke({
    "input_url": "https://clinicaltrials.gov/study/NCT03991871",
    "input_type": "unknown",
    "chat_query": "What is the primary objective?",
    # ... other state fields
})

print(f"Confidence: {result['confidence_score']}")
print(f"Response: {result['chat_response']}")
```

### Interactive Chat

```python
# After processing document
result["chat_query"] = "What are the eligibility criteria?"
result = app.invoke(result)
print(result["chat_response"])
```

## 📋 Extracted Fields

The workflow extracts 9 standard fields:

1. **study_overview** - Title and study design
2. **brief_description** - Summary
3. **primary_secondary_objectives** - Endpoints
4. **treatment_arms_interventions** - Study arms and drugs
5. **eligibility_criteria** - Inclusion/exclusion
6. **enrollment_participant_flow** - Patient numbers
7. **adverse_events_profile** - Safety data
8. **study_locations** - Sites
9. **sponsor_information** - Sponsors and collaborators

## 🎨 Streamlit UI Features

### Input Tab
- ClinicalTrials.gov URL input
- PDF file upload
- PDF URL input

### Chat Tab
- Automatic summary generation
- Interactive Q&A
- Context-aware responses

### Data View Tab
- Field-by-field extraction status
- Quality metrics
- Missing field indicators
- JSON download

### Sidebar
- Real-time metrics
- Confidence/completeness scores
- Missing fields list
- JSON download button

## 🔍 Quality Metrics

### Confidence Score (0-1)
- Based on content richness
- Measures extraction quality
- Triggers LLM fallback if < 0.5

### Completeness Score (0-1)
- Percentage of required fields filled
- Tracks missing data
- Triggers LLM fallback if < 0.6

## 🤖 LLM Fallback

When quality is low:
1. Extract full document text
2. Send to GPT-4 with structured prompt
3. Extract missing fields
4. Preserve original content exactly
5. Merge with existing data

## 📁 File Structure

```
langgraph_workflow.py       # Main workflow implementation
test_langgraph_workflow.py  # Tests and visualization
app_langgraph.py            # Streamlit UI
requirements_langgraph.txt  # Dependencies
```

## 🛠️ Implementation Notes

### Following LangGraph Patterns

1. **State Management**: TypedDict for type safety
2. **Node Functions**: Simple, focused functions
3. **Conditional Edges**: Clean routing logic
4. **Graph Builder**: Standard StateGraph pattern
5. **No Custom Code**: Using official APIs only

### Design Decisions

- **Simple over complex**: Minimal custom logic
- **Official patterns**: Following LangGraph docs
- **Type safety**: TypedDict for state
- **Error handling**: Graceful fallbacks
- **Modular**: Each node has single responsibility

## 🧪 Testing

The test file provides:
- URL parsing test
- PDF parsing test
- Interactive chat test
- Graph visualization
- Results in JSON format

## 🔗 Integration with Existing Code

- Uses existing `enhanced_parser.py` for PDF parsing
- Uses existing `clinical_trail_parser.py` for schema mapping
- Compatible with `app_v1.py` data structures
- Preserves confidence/completeness metrics from tests

## 📚 References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 🎯 Next Steps

1. Run tests to verify setup
2. Check graph visualization
3. Launch Streamlit app
4. Test with your documents
5. Review metrics and adjust thresholds

## 💡 Tips

- Start with URL input for fastest testing
- Check confidence scores to tune thresholds
- Use chat for specific field queries
- Download JSON for further processing
- Review missing fields to improve prompts
