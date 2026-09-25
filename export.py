import os
import uuid
from typing import List, Dict, Any
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

EXPORT_DIR = os.environ.get("EXPORT_DIR", "./exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


def export_to_xlsx(rows: List[Dict[str, Any]], filename: str | None = None) -> str:
    """
    Simpan list of dict jadi file .xlsx, return path filenya.
    """
    if not rows:
        rows = []
    df = pd.DataFrame(rows)
    filename = filename or f"projects_{uuid.uuid4().hex[:8]}.xlsx"
    if not filename.endswith(".xlsx"):
        filename += ".xlsx"
    path = os.path.join(EXPORT_DIR, filename)
    df.to_excel(path, index=False, engine="openpyxl")
    return path