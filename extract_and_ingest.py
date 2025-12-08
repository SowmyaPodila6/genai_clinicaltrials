#!/usr/bin/env python3
"""
Quick Clinical Trials Extraction and Ingestion Script
Run this to download 100 studies and load them into the vector database
"""

import sys
import os
import time
from pathlib import Path
import logging

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Main extraction and ingestion function"""
    print("🚀 Clinical Trials Data Extraction & Ingestion")
    print("=" * 50)
    
    try:
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
        
        # Import modules
        print("📦 Importing modules...")
        from langgraph_custom.clinical_trials_downloader import ClinicalTrialsDownloader
        from langgraph_custom.vector_db_manager import ClinicalTrialsVectorDB
        
        # Ensure directories exist
        print("📁 Creating directories...")
        Path('data').mkdir(exist_ok=True)
        Path('db').mkdir(exist_ok=True)
        
        # Initialize downloader
        print("🔧 Initializing clinical trials downloader...")
        downloader = ClinicalTrialsDownloader()
        
        # Download clinical trials (100 studies)
        print("📥 Downloading clinical trials studies...")
        print("   Using known cancer clinical trials for demo...")
        
        # Use known NCT IDs for reliable demo data
        known_nct_ids = [
            "NCT03991871", "NCT04640688", "NCT03986879", "NCT04577859", "NCT04556435",
            "NCT04380701", "NCT04261777", "NCT04042480", "NCT03812549", "NCT03729765",
            "NCT03616470", "NCT03604614", "NCT03603379", "NCT03581435", "NCT03575572",
            "NCT03971409", "NCT03914820", "NCT03875092", "NCT03834948", "NCT03794544",
            "NCT03762785", "NCT03745170", "NCT03739931", "NCT03718091", "NCT03713905",
            "NCT03698383", "NCT03683225", "NCT03667716", "NCT03633110", "NCT03624231",
            "NCT03590561", "NCT03574532", "NCT03568058", "NCT03549169", "NCT03533426",
            "NCT03529331", "NCT03515785", "NCT03495752", "NCT03484923", "NCT03475823",
            "NCT03425097", "NCT03414983", "NCT03366129", "NCT03353402", "NCT03343301",
            "NCT03337698", "NCT03317327", "NCT03307785", "NCT03304093", "NCT03298113",
            "NCT03290833", "NCT03289962", "NCT03280056", "NCT03277625", "NCT03273712",
            "NCT03272477", "NCT03267940", "NCT03258255", "NCT03257462", "NCT03256136",
            "NCT03249688", "NCT03244280", "NCT03239392", "NCT03226886", "NCT03220477",
            "NCT03215030", "NCT03214250", "NCT03209973", "NCT03204253", "NCT03203616",
            "NCT03155620", "NCT03150056", "NCT03135834", "NCT03135301", "NCT03117309",
            "NCT03113032", "NCT03110445", "NCT03104699", "NCT03099109", "NCT03086239",
            "NCT03081923", "NCT03075085", "NCT03074513", "NCT03063450", "NCT03061305",
            "NCT03056612", "NCT03052049", "NCT03051048", "NCT03044327", "NCT03040310",
            "NCT03033225", "NCT03032354", "NCT03024021", "NCT03022409", "NCT03012230",
            "NCT02997176", "NCT02996058", "NCT02993211", "NCT02983045", "NCT02973282"
        ]
        
        # Process each NCT ID
        print(f"   Processing {len(known_nct_ids)} known cancer clinical trials...")
        
        processed_trials = []
        failed_count = 0
        
        for i, nct_id in enumerate(known_nct_ids[:100], 1):  # Limit to 100
            if i % 20 == 0:
                print(f"   Processed {i}/{len(known_nct_ids[:100])} trials...")
            
            try:
                study_data = downloader.extract_study_data(nct_id)
                if study_data:
                    processed_trials.append(study_data)
                else:
                    failed_count += 1
                
                # Rate limiting
                time.sleep(0.2)
                
            except Exception as e:
                print(f"   ⚠️  Failed to process {nct_id}: {e}")
                failed_count += 1
                continue
        
        # Save to JSON
        json_file = 'data/cancer_clinical_trials_100.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(processed_trials, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully processed {len(processed_trials)} trials")
        if failed_count > 0:
            print(f"⚠️  Failed to process {failed_count} trials")
        
        print(f"✅ Clinical trials data saved to: {json_file}")
        
        # Initialize vector database
        print("🗄️  Initializing vector database...")
        vector_db = ClinicalTrialsVectorDB(
            db_path="db/clinical_trials_vectordb",
            collection_name="cancer_clinical_trials"
        )
        
        # Load studies into vector database
        print("📚 Loading studies into vector database...")
        studies_loaded = vector_db.load_from_json(json_file)
        
        if studies_loaded > 0:
            print(f"✅ Successfully loaded {studies_loaded} studies into vector database!")
            
            # Get and display statistics
            print("📊 Vector Database Statistics:")
            stats = vector_db.get_collection_stats()
            print(f"   📈 Total studies: {stats.get('total_studies', 0)}")
            print(f"   📊 Collection: {stats.get('collection_name', 'N/A')}")
            print(f"   🔬 Embedding model: {stats.get('embedding_model', 'N/A')}")
            
            # Show status distribution
            status_dist = stats.get('status_distribution', {})
            if status_dist:
                print("   📋 Study status distribution:")
                for status, count in status_dist.items():
                    print(f"      - {status}: {count}")
            
            # Test search functionality
            print("🧪 Testing search functionality...")
            try:
                results = vector_db.search_by_drug("pembrolizumab", n_results=3)
                if results:
                    print(f"   ✅ Found {len(results)} similar studies for 'pembrolizumab'")
                    print("   📋 Sample results:")
                    for i, result in enumerate(results[:2], 1):
                        print(f"      {i}. {result['nct_id']}: {result['brief_title'][:60]}...")
                        print(f"         Similarity: {result['similarity_score']:.3f}")
                else:
                    print("   ⚠️  No results found (this might be normal with limited data)")
            except Exception as e:
                print(f"   ⚠️  Search test failed: {e}")
        
        else:
            print("❌ No studies were loaded into the database")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 SUCCESS! Your vector database is ready!")
        print("\n💡 Next steps:")
        print("   1. Run your Streamlit app: streamlit run UI/app.py")
        print("   2. Ask questions like: 'Can you find similar studies using pembrolizumab?'")
        print("   3. The system will automatically search the vector database!")
        print(f"\n📂 Database location: db/clinical_trials_vectordb/")
        print(f"📄 Data file: {json_file}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try installing missing dependencies:")
        print("   pip install chromadb sentence-transformers langchain-community")
        return False
        
    except Exception as e:
        print(f"❌ Error during extraction/ingestion: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("\n🚀 Ready to use the RAG system!")