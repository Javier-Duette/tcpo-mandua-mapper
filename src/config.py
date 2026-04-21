from pathlib import Path
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = ROOT / "data" / "precios.db"
MANDUA_XLSX = ROOT / "data" / "datos-mandua-marzo-26.xlsx"
TCPO_XLSX = ROOT / "data" / "tcpo-versao-15.xlsx"
OUTPUT_DIR = ROOT / "output"
