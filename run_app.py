"""
Launcher script for the Health Monitor Streamlit app.
This script ensures the app module is in the Python path.
"""
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run the main app
if __name__ == "__main__":
    import streamlit.web.cli as stcli
    import os
    
    # Set the main script path
    main_script = project_root / "app" / "main.py"
    
    # Run streamlit with the main script
    sys.argv = ["streamlit", "run", str(main_script)]
    sys.exit(stcli.main())
