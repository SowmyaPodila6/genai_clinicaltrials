#!/usr/bin/env python3
"""
Debug re-extraction flow without requiring API calls
"""

import sys
import json
import sqlite3
import os
from pathlib import Path
sys.path.insert(0, str(Path('.').absolute()))

def analyze_reextraction_messages():
    """Analyze the database to see if re-extractions are actually happening"""
    
    print("=== ANALYZING RE-EXTRACTION ACTIVITY ===")
    
    DB_FILE = 'data/chat_history.db'
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check for re-extraction messages in chat history
    print("🔍 Looking for re-extraction messages...")
    c.execute('''SELECT conversation_id, role, content, message_type, timestamp, metadata 
                 FROM chat_messages 
                 WHERE message_type IN ('re-extraction', 're-extracted_content')
                 ORDER BY timestamp DESC LIMIT 10''')
    
    reextraction_msgs = c.fetchall()
    
    if not reextraction_msgs:
        print("❌ No re-extraction messages found in database!")
        print("💡 This suggests re-extraction has never been attempted")
        return False
    
    print(f"✅ Found {len(reextraction_msgs)} re-extraction related messages:")
    
    for conv_id, role, content, msg_type, timestamp, metadata in reextraction_msgs:
        print(f"\n📅 {timestamp} | {role} | {msg_type}")
        print(f"🔧 Content: {content[:100]}...")
        
        if metadata:
            try:
                meta_data = json.loads(metadata)
                if 'field' in meta_data:
                    print(f"🎯 Field: {meta_data['field']}")
                if 'feedback' in meta_data:
                    print(f"💬 Feedback: {meta_data['feedback'][:100]}...")
                if 'success' in meta_data:
                    print(f"✅ Success: {meta_data['success']}")
            except:
                pass
    
    # Check extraction states for actual content changes
    print(f"\n🔍 Checking for actual content changes in extraction states...")
    
    # Get conversations that had re-extraction activity
    reextraction_convs = list(set([msg[0] for msg in reextraction_msgs]))
    
    content_changes_found = 0
    
    for conv_id in reextraction_convs[:3]:  # Check top 3 conversations
        print(f"\n📋 Analyzing conversation: {conv_id}")
        
        c.execute('SELECT state_json, updated_at FROM extraction_states WHERE conversation_id = ?', (conv_id,))
        state_row = c.fetchone()
        
        if state_row:
            try:
                state = json.loads(state_row[0])
                parsed_json = state.get('parsed_json', {})
                
                # Look for evidence of re-extraction in content
                for field_name, field_data in parsed_json.items():
                    if isinstance(field_data, dict) and 'content' in field_data:
                        content = field_data['content']
                        
                        # Check for our test markers or signs of re-extraction
                        if any(marker in content for marker in [
                            '[RE-EXTRACTED',
                            'addressing the user feedback',
                            'based on your feedback',
                            'as requested in the feedback'
                        ]):
                            print(f"✅ Found evidence of re-extraction in field '{field_name}'")
                            print(f"📄 Content preview: {content[:200]}...")
                            content_changes_found += 1
                        else:
                            print(f"📄 Field '{field_name}': {len(content)} chars, no re-extraction markers")
                            
            except Exception as e:
                print(f"❌ Error parsing state for {conv_id}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   - Re-extraction messages in DB: {len(reextraction_msgs)}")
    print(f"   - Conversations analyzed: {len(reextraction_convs)}")
    print(f"   - Content changes found: {content_changes_found}")
    
    if content_changes_found > 0:
        print("✅ Evidence suggests re-extraction is working!")
        return True
    else:
        print("⚠️ No clear evidence of successful content changes from re-extraction")
        return False

def check_ui_reextraction_flow():
    """Check if the UI re-extraction flow has the right components"""
    
    print("\n=== CHECKING UI RE-EXTRACTION FLOW ===")
    
    try:
        # Check if the UI app file has the re-extraction function
        app_file = Path("UI/app.py")
        if not app_file.exists():
            print("❌ UI/app.py not found")
            return False
        
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key components
        checks = {
            "_reextract_field_with_feedback": "Re-extraction function exists",
            "extract_field_with_feedback": "Calls MultiTurnExtractor method", 
            "MultiTurnExtractor": "Uses the extractor class",
            "feedback": "Handles user feedback parameter",
            "refined_result": "Processes LLM results",
            "st.session_state.current_state": "Updates session state",
            "save_extraction_state": "Persists to database"
        }
        
        missing_components = []
        found_components = []
        
        for component, description in checks.items():
            if component in content:
                found_components.append(f"✅ {description}")
            else:
                missing_components.append(f"❌ {description}")
        
        print("UI Component Analysis:")
        for item in found_components:
            print(f"  {item}")
        for item in missing_components:
            print(f"  {item}")
        
        if len(found_components) >= 6:  # Most components found
            print("✅ UI re-extraction flow appears to be properly implemented")
            return True
        else:
            print("❌ UI re-extraction flow is missing key components")
            return False
            
    except Exception as e:
        print(f"❌ Error checking UI file: {e}")
        return False

def check_openai_config():
    """Check if OpenAI is properly configured"""
    
    print("\n=== CHECKING OPENAI CONFIGURATION ===")
    
    api_key = os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("💡 Re-extraction requires OpenAI API access")
        print("🔧 Set your API key with: $env:OPENAI_API_KEY='your-key'")
        return False
    else:
        # Mask the key for security
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"✅ OPENAI_API_KEY is set: {masked_key}")
        return True

def test_extractor_instantiation():
    """Test if MultiTurnExtractor can be instantiated"""
    
    print("\n=== TESTING EXTRACTOR INSTANTIATION ===")
    
    try:
        # Try to import and instantiate without making API calls
        from langgraph_custom.multi_turn_extractor import MultiTurnExtractor
        
        if not os.environ.get('OPENAI_API_KEY'):
            print("⚠️ Skipping instantiation test - no API key")
            return False
        
        print("🧪 Attempting to create MultiTurnExtractor instance...")
        extractor = MultiTurnExtractor(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens_per_call=180000
        )
        
        print("✅ MultiTurnExtractor instantiated successfully!")
        print(f"📊 Model: {extractor.llm.model_name}")
        print(f"🌡️ Temperature: {extractor.llm.temperature}")
        
        # Check if the extractor has the right method
        if hasattr(extractor, 'extract_field_with_feedback'):
            print("✅ extract_field_with_feedback method exists")
            return True
        else:
            print("❌ extract_field_with_feedback method missing")
            return False
            
    except Exception as e:
        print(f"❌ Error instantiating MultiTurnExtractor: {e}")
        return False

if __name__ == "__main__":
    print("=== RE-EXTRACTION DEBUG ANALYSIS ===\n")
    
    # Run all checks
    results = {
        "Database activity": analyze_reextraction_messages(),
        "UI flow": check_ui_reextraction_flow(),
        "OpenAI config": check_openai_config(),
        "Extractor instantiation": test_extractor_instantiation()
    }
    
    print(f"\n{'='*50}")
    print("FINAL DIAGNOSIS:")
    
    for check_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL" 
        print(f"  {check_name}: {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Re-extraction system appears to be working correctly!")
    elif passed >= 2:
        print("⚠️ System partially working - check failed components")
    else:
        print("❌ Re-extraction system has significant issues")
        
    print("\n💡 If re-extraction seems to not work in UI:")
    print("   1. Ensure OPENAI_API_KEY is set correctly")
    print("   2. Check that you're providing meaningful feedback")
    print("   3. Verify the PDF text was cached properly")
    print("   4. Look for error messages in the Streamlit UI")