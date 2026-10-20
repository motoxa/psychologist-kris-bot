import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_base64 = os.getenv("GCP_CREDS_BASE64")
if creds_base64:
    creds_json = base64.b64decode(creds_base64).decode("utf-8")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PATH_TO_CREDS = os.path.join(BASE_DIR, "creds.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(PATH_TO_CREDS, scope)

client = gspread.authorize(creds)
sheet_start = client.open_by_key(os.getenv("SHEET_ID_START")).sheet1
