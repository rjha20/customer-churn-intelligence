from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "src" / "customer_churn" / "pipeline.py"), run_name="__main__")
