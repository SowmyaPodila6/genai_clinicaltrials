"""
Setup Script for Clinical Trials RAG System
Downloads cancer clinical trials data and initializes vector database
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from langgraph_custom.clinical_trials_downloader import ClinicalTrialsDownloader
from langgraph_custom.vector_db_manager import ClinicalTrialsVectorDB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('setup_rag_system.log')
    ]
)
logger = logging.getLogger(__name__)


def ensure_directories():
    """Ensure required directories exist"""
    directories = ['data', 'db', 'db/clinical_trials_vectordb']
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Directory ensured: {dir_path}")


def download_clinical_trials_data(force_refresh=False):
    """Download cancer clinical trials data"""
    data_file = Path("data/cancer_clinical_trials.json")
    
    # Check if data already exists
    if data_file.exists() and not force_refresh:
        file_size = data_file.stat().st_size
        logger.info(f"📂 Clinical trials data already exists: {data_file} ({file_size:,} bytes)")
        
        # Ask user if they want to refresh
        response = input("Data file already exists. Do you want to refresh it? (y/N): ")
        if response.lower() != 'y':
            logger.info("Using existing data file")
            return str(data_file)
    
    logger.info("🚀 Downloading cancer clinical trials data...")
    
    downloader = ClinicalTrialsDownloader()
    
    try:
        # Download with focus on major cancer types and popular immunotherapy drugs
        output_file = downloader.download_cancer_trials(
            output_file=str(data_file),
            max_studies=800,  # Reasonable number for initial setup
            conditions=[
                "lung cancer", "breast cancer", "colorectal cancer", "melanoma",
                "lymphoma", "leukemia", "ovarian cancer", "prostate cancer",
                "pancreatic cancer", "kidney cancer", "bladder cancer", 
                "brain tumor", "glioblastoma", "sarcoma", "liver cancer"
            ],
            interventions=[
                # Popular immunotherapy drugs
                "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", 
                "ipilimumab", "avelumab", "cemiplimab",
                # Popular targeted therapies
                "bevacizumab", "trastuzumab", "rituximab", "cetuximab",
                # Common chemotherapy
                "carboplatin", "cisplatin", "paclitaxel", "docetaxel"
            ]
        )
        
        logger.info(f"✅ Clinical trials data downloaded to: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"❌ Failed to download clinical trials data: {e}")
        raise


def setup_vector_database(json_file_path):
    """Initialize vector database with clinical trials data"""
    logger.info("🔧 Setting up vector database...")
    
    try:
        # Initialize vector database
        vector_db = ClinicalTrialsVectorDB(
            db_path="db/clinical_trials_vectordb",
            collection_name="cancer_clinical_trials",
            embedding_model="all-MiniLM-L6-v2"  # Fast and good quality
        )
        
        # Load data from JSON file
        logger.info(f"📚 Loading clinical trials data from {json_file_path}...")
        studies_loaded = vector_db.load_from_json(json_file_path)
        
        if studies_loaded > 0:
            logger.info(f"✅ Successfully loaded {studies_loaded} studies into vector database")
            
            # Get and display statistics
            stats = vector_db.get_collection_stats()
            logger.info("📊 Vector database statistics:")
            logger.info(f"   Total studies: {stats.get('total_studies', 0)}")
            logger.info(f"   Status distribution: {stats.get('status_distribution', {})}")
            logger.info(f"   Study types: {stats.get('study_type_distribution', {})}")
            logger.info(f"   Phases: {stats.get('phase_distribution', {})}")
            
            return vector_db
        else:
            logger.warning("⚠️  No studies were loaded into the vector database")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to setup vector database: {e}")
        raise


def test_rag_functionality(vector_db):
    """Test RAG functionality with sample queries"""
    logger.info("🧪 Testing RAG functionality...")
    
    test_drugs = ["pembrolizumab", "nivolumab", "bevacizumab", "trastuzumab"]
    
    for drug in test_drugs:
        try:
            logger.info(f"   Testing search for: {drug}")
            results = vector_db.search_by_drug(drug, n_results=3)
            
            if results:
                logger.info(f"   ✅ Found {len(results)} similar studies for {drug}")
                for i, result in enumerate(results[:2], 1):
                    logger.info(f"      {i}. {result['nct_id']}: {result['brief_title'][:60]}... (similarity: {result['similarity_score']:.3f})")
            else:
                logger.warning(f"   ⚠️  No results found for {drug}")
                
        except Exception as e:
            logger.error(f"   ❌ Error testing {drug}: {e}")
    
    logger.info("✅ RAG functionality testing completed")


def test_langgraph_integration():
    """Test LangGraph workflow integration"""
    logger.info("🔗 Testing LangGraph integration...")
    
    try:
        from langgraph_custom.rag_tool import create_clinical_trials_rag_tool
        
        # Test tool creation
        rag_tool = create_clinical_trials_rag_tool()
        logger.info("✅ RAG tool created successfully")
        
        # Test tool functionality
        result = rag_tool._run("pembrolizumab", n_results=2)
        if result and not result.startswith("Error"):
            logger.info("✅ RAG tool executed successfully")
            logger.info(f"   Sample result preview: {result[:200]}...")
        else:
            logger.warning(f"⚠️  RAG tool returned error: {result[:100]}...")
            
    except Exception as e:
        logger.error(f"❌ LangGraph integration test failed: {e}")
        raise


def main():
    """Main setup function"""
    print("🚀 Setting up Clinical Trials RAG System")
    print("=" * 50)
    
    start_time = datetime.now()
    
    try:
        # Step 1: Ensure directories exist
        print("\n📁 Step 1: Setting up directories...")
        ensure_directories()
        
        # Step 2: Download clinical trials data
        print("\n📥 Step 2: Downloading clinical trials data...")
        json_file = download_clinical_trials_data()
        
        # Step 3: Setup vector database
        print("\n🔧 Step 3: Setting up vector database...")
        vector_db = setup_vector_database(json_file)
        
        if not vector_db:
            raise Exception("Vector database setup failed")
        
        # Step 4: Test functionality
        print("\n🧪 Step 4: Testing RAG functionality...")
        test_rag_functionality(vector_db)
        
        # Step 5: Test LangGraph integration
        print("\n🔗 Step 5: Testing LangGraph integration...")
        test_langgraph_integration()
        
        # Success summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 50)
        print("🎉 Clinical Trials RAG System Setup Complete!")
        print(f"⏱️  Total setup time: {duration}")
        print("\n📋 What's been set up:")
        print("   ✅ Vector database with cancer clinical trials")
        print("   ✅ RAG tool for similarity search")
        print("   ✅ LangGraph workflow integration")
        print("\n🚀 Ready to use!")
        print("\nTo test the system:")
        print("   1. Run the Streamlit app: streamlit run UI/app.py")
        print("   2. Ask questions like: 'Can you find similar studies using pembrolizumab?'")
        print("   3. The system will automatically search the vector database and provide relevant clinical trials")
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        print(f"\n❌ Setup failed: {e}")
        print("Check setup_rag_system.log for detailed error information.")
        sys.exit(1)


if __name__ == "__main__":
    main()