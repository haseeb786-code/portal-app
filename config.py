import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ODOCUST Portal Configuration
ODOCUST_BASE_URL = os.getenv("ODOCUST_BASE_URL", "https://odoo.cust.edu.pk").rstrip("/")
ODOCUST_USERNAME = os.getenv("ODOCUST_USERNAME", "")
ODOCUST_EMAIL = os.getenv("ODOCUST_EMAIL", f"{ODOCUST_USERNAME}@cust.pk")
ODOCUST_PASSWORD = os.getenv("ODOCUST_PASSWORD", "")
ODOCUST_SESSION_ID = os.getenv("ODOCUST_SESSION_ID", "")  # Optional direct cookie

# Monitoring Configuration
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
REMINDER_HOURS = [int(h.strip()) for h in os.getenv("REMINDER_HOURS", "72,48,24,12,6,3,1").split(",")]

# WhatsApp Configuration
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "true").lower() in ("true", "1", "yes")
# Providers: 'console_log', 'twilio', 'greenapi', 'callmebot', 'meta'
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "console_log").lower()
WHATSAPP_TO_NUMBER = os.getenv("WHATSAPP_TO_NUMBER", "")

# Twilio Settings
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# Green-API Settings
GREENAPI_INSTANCE_ID = os.getenv("GREENAPI_INSTANCE_ID", "")
GREENAPI_API_TOKEN = os.getenv("GREENAPI_API_TOKEN", "")

# CallMeBot Settings
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", "")
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "")

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_USERNAME = os.getenv("TELEGRAM_USERNAME", "")

# Meta Cloud API Settings
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

# Daily Summary Configuration
DAILY_SUMMARY_ENABLED = os.getenv("DAILY_SUMMARY_ENABLED", "true").lower() in ("true", "1", "yes")
DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "08:00")  # HH:MM format

# Server & Dashboard Configuration
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))
DATABASE_PATH = str(BASE_DIR / os.getenv("DATABASE_PATH", "odocust_monitor.db"))

# AI Copilot & Academic Profile Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
AI_AGENT_ENABLED = os.getenv("AI_AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
STUDENT_CURRENT_CGPA = float(os.getenv("STUDENT_CURRENT_CGPA", "2.53"))
STUDENT_TARGET_GPA = float(os.getenv("STUDENT_TARGET_GPA", "4.00"))
STUDENT_COMPLETED_CREDITS = int(os.getenv("STUDENT_COMPLETED_CREDITS", "104"))

