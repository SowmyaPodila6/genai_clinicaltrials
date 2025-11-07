"""
Install spaCy language model for Streamlit Cloud deployment.
This script is called during deployment to download the required language model.
"""

import subprocess
import sys
import os

def install_spacy_model():
    """Download and install spaCy English model."""
    try:
        print("📥 Downloading spaCy English model...")
        
        # Try to import spacy first
        import spacy
        
        # Check if model already exists
        try:
            nlp = spacy.load("en_core_web_sm")
            print("✅ spaCy model already installed!")
            return True
        except OSError:
            pass
        
        # Download the model
        subprocess.check_call([
            sys.executable, 
            "-m", 
            "spacy", 
            "download", 
            "en_core_web_sm"
        ])
        
        print("✅ spaCy model installed successfully!")
        return True
        
    except Exception as e:
        print(f"⚠️  Warning: Could not install spaCy model: {e}")
        print("   The application will work without NLP features.")
        return False

if __name__ == "__main__":
    install_spacy_model()
