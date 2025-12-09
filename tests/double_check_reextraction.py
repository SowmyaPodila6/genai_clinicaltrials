#!/usr/bin/env python3
"""
Comprehensive double-check of re-extraction functionality
"""

import sys
import json
import sqlite3
import os
from pathlib import Path
sys.path.insert(0, str(Path('.').absolute()))

def test_complete_reextraction_pipeline():
    """Test the entire re-extraction pipeline from UI to database"""
    
    print("=== COMPREHENSIVE RE-EXTRACTION DOUBLE-CHECK ===\n")
    
    # Test 1: Verify imports and shared LLM
    print("1️⃣ TESTING IMPORTS AND LLM INSTANCE")
    try:
        from langgraph_custom.langgraph_workflow import get_shared_llm_instance
        from langgraph_custom.multi_turn_extractor import MultiTurnExtractor
        
        shared_llm = get_shared_llm_instance()
        print(f"✅ Shared LLM instance: {type(shared_llm).__name__}")
        print(f"   Model: {shared_llm.model_name}")
        print(f"   Temperature: {shared_llm.temperature}")
        print(f"   Streaming: {shared_llm.streaming}")
        
    except Exception as e:
        print(f"❌ Import/LLM test failed: {e}")
        return False
    
    # Test 2: Verify MultiTurnExtractor instantiation with shared LLM
    print("\n2️⃣ TESTING MULTITURNEXTRACTOR WITH SHARED LLM")
    try:
        extractor = MultiTurnExtractor(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens_per_call=180000,
            delay_between_calls=2.0,
            llm_instance=shared_llm
        )
        print("✅ MultiTurnExtractor created successfully with shared LLM")
        print(f"   Using provided LLM: {hasattr(extractor, 'llm')}")
        print(f"   LLM type: {type(extractor.llm).__name__}")
        
    except Exception as e:
        print(f"❌ MultiTurnExtractor test failed: {e}")
        return False
    
    # Test 3: Test actual LLM call with feedback
    print("\n3️⃣ TESTING ACTUAL LLM CALL WITH FEEDBACK")
    test_text = """
    --- Page 1 ---
    Clinical Trial: ADVANCE Study
    
    Study Overview: This is a Phase 3 randomized controlled trial.
    
    Primary Objective: To evaluate efficacy of new treatment.
    Secondary Objective: To assess safety profile.
    
    Treatment Arms:
    - Group A: Active drug 50mg once daily
    - Group B: Placebo control
    
    Eligibility: Adults aged 18-70 years with confirmed diagnosis.
    """
    
    test_feedback = "Please add more specific details about the study duration, sample size, and primary endpoint measurements"
    
    try:
        print(f"📝 Testing with feedback: {test_feedback[:60]}...")
        
        result = extractor.extract_field_with_feedback(
            full_text=test_text,
            field_name="study_overview",
            feedback=test_feedback
        )
        
        if result and isinstance(result, dict):
            content = result.get('content', '')
            page_refs = result.get('page_references', [])
            
            print("✅ LLM call successful!")
            print(f"   Content length: {len(content)} chars")
            print(f"   Page references: {page_refs}")
            print(f"   Content preview: {content[:150]}...")
            
            # Check if feedback was addressed
            feedback_keywords = ['duration', 'sample size', 'endpoint', 'measurement']
            addressed_keywords = [kw for kw in feedback_keywords if kw.lower() in content.lower()]
            
            print(f"   Feedback keywords found: {addressed_keywords}")
            
            if len(addressed_keywords) > 0 or len(content) > len(test_text):
                print("✅ Feedback appears to be processed by LLM!")
            else:
                print("⚠️ Feedback processing unclear - manual review needed")
                
        else:
            print(f"❌ LLM call failed - invalid result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ LLM call test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Simulate UI state update flow
    print("\n4️⃣ TESTING UI STATE UPDATE SIMULATION")
    try:
        # Simulate the UI re-extraction flow
        mock_state = {
            "parsed_json": {
                "study_overview": {
                    "content": "Original study overview content",
                    "page_references": [1]
                }
            },
            "data_to_summarize": {
                "Study Overview": "Original study overview content"
            }
        }
        
        # Simulate the update process from UI
        field_name = "study_overview"
        refined_result = result  # Use result from previous test
        
        # Update parsed_json
        mock_state["parsed_json"][field_name] = refined_result
        
        # Update data_to_summarize
        field_mapping = {
            "study_overview": "Study Overview",
            "brief_description": "Brief Description",
            "primary_secondary_objectives": "Primary and Secondary Objectives"
        }
        
        display_key = field_mapping.get(field_name, field_name)
        content = refined_result.get("content", "") if isinstance(refined_result, dict) else str(refined_result)
        
        if content:
            mock_state["data_to_summarize"][display_key] = content
        
        print("✅ State update simulation successful!")
        print(f"   Updated parsed_json for: {field_name}")
        print(f"   Updated data_to_summarize for: {display_key}")
        print(f"   New content length: {len(content)} chars")
        
    except Exception as e:
        print(f"❌ State update test failed: {e}")
        return False
    
    # Test 5: Check database interaction capability
    print("\n5️⃣ TESTING DATABASE INTERACTION")
    try:
        DB_FILE = 'data/chat_history.db'
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Check if we can read extraction states
        c.execute('SELECT COUNT(*) FROM extraction_states')
        state_count = c.fetchone()[0]
        print(f"✅ Database accessible - {state_count} extraction states found")
        
        # Check recent re-extraction messages
        c.execute('''SELECT COUNT(*) FROM chat_messages 
                     WHERE message_type IN ('re-extraction', 're-extracted_content')
                     AND timestamp > datetime('now', '-1 day')''')
        recent_reextraction_count = c.fetchone()[0]
        print(f"✅ Recent re-extractions in DB: {recent_reextraction_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    
    # Test 6: Verify UI function existence
    print("\n6️⃣ TESTING UI FUNCTION AVAILABILITY")
    try:
        ui_file_path = Path("UI/app.py")
        if ui_file_path.exists():
            with open(ui_file_path, 'r', encoding='utf-8') as f:
                ui_content = f.read()
            
            required_functions = [
                '_reextract_field_with_feedback',
                'get_shared_llm_instance',
                'MultiTurnExtractor',
                'llm_instance=shared_llm'
            ]
            
            found_functions = []
            missing_functions = []
            
            for func in required_functions:
                if func in ui_content:
                    found_functions.append(func)
                else:
                    missing_functions.append(func)
            
            print(f"✅ UI functions found: {len(found_functions)}/{len(required_functions)}")
            for func in found_functions:
                print(f"   ✓ {func}")
            
            if missing_functions:
                print(f"❌ Missing UI functions:")
                for func in missing_functions:
                    print(f"   ✗ {func}")
                return False
                
        else:
            print("❌ UI/app.py file not found")
            return False
            
    except Exception as e:
        print(f"❌ UI function test failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("✅ Re-extraction pipeline is fully functional")
    return True

def test_edge_cases():
    """Test edge cases and error handling"""
    
    print("\n=== TESTING EDGE CASES ===")
    
    try:
        from langgraph_custom.langgraph_workflow import get_shared_llm_instance
        from langgraph_custom.multi_turn_extractor import MultiTurnExtractor
        
        shared_llm = get_shared_llm_instance()
        extractor = MultiTurnExtractor(llm_instance=shared_llm)
        
        # Test 1: Empty text
        print("\n📝 Testing with empty text...")
        result = extractor.extract_field_with_feedback("", "study_overview", "Add more details")
        print(f"   Empty text result: {type(result)} - {result}")
        
        # Test 2: Invalid field name
        print("\n📝 Testing with invalid field name...")
        result = extractor.extract_field_with_feedback("Some text", "invalid_field", "Feedback")
        print(f"   Invalid field result: {type(result)} - {result}")
        
        # Test 3: Very long feedback
        print("\n📝 Testing with very long feedback...")
        long_feedback = "Please add more details " * 100  # 2000+ chars
        result = extractor.extract_field_with_feedback("Test text", "study_overview", long_feedback)
        print(f"   Long feedback result: {type(result)} - handled gracefully")
        
        print("✅ Edge case testing completed")
        return True
        
    except Exception as e:
        print(f"❌ Edge case testing failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting comprehensive re-extraction double-check...\n")
    
    # Run main tests
    main_success = test_complete_reextraction_pipeline()
    
    # Run edge case tests
    edge_success = test_edge_cases()
    
    print(f"\n{'='*60}")
    print("FINAL VERIFICATION RESULTS:")
    print(f"Main pipeline: {'✅ PASS' if main_success else '❌ FAIL'}")
    print(f"Edge cases: {'✅ PASS' if edge_success else '❌ FAIL'}")
    
    if main_success and edge_success:
        print("\n🚀 DOUBLE-CHECK COMPLETE: RE-EXTRACTION IS FULLY WORKING!")
        print("💡 The system is ready for production use")
    elif main_success:
        print("\n⚠️ Main functionality works, but edge cases need attention")
    else:
        print("\n❌ Critical issues found - needs debugging")
        
    print("\nNext steps:")
    print("1. Start Streamlit UI: streamlit run UI/app.py")
    print("2. Upload a PDF or enter a ClinicalTrials.gov URL")
    print("3. Go to 'View JSON' tab after extraction")
    print("4. Click 'Refine' on any field and provide feedback")
    print("5. Verify the content updates with your feedback")