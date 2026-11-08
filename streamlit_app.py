"""Entry point for Streamlit Community Cloud (and `streamlit run streamlit_app.py`)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).parent / "src" / "pensionlab" / "lab" / "app.py"), run_name="__main__")
