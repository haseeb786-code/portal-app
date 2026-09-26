import logging
import threading
import time
import time
import sys

# Ensure UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import uvicorn

import config
from core.database import Database
from core.auth import OdoCustAuth
from core.extractor import OdoCustExtractor
from notifier.whatsapp import get_whatsapp_notifier
from engine.monitor import AcademicMonitorAgent
from dashboard.app import create_dashboard_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("odocust_agent.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("odocust.main")

def run_scheduler_loop(monitor_agent: AcademicMonitorAgent, database: Database):
    """
    Background worker that runs monitoring cycles at regular intervals.
    """
    logger.info("Background monitoring worker started.")
    
    # Run initial check cycle on startup
    try:
        monitor_agent.run_check_cycle()
    except Exception as e:
        logger.error(f"Error in initial monitoring cycle: {e}")

    while True:
        # Fetch interval from settings in case user changed it in dashboard
        try:
            interval_mins = int(database.get_setting("check_interval_minutes", str(config.CHECK_INTERVAL_MINUTES)))
        except ValueError:
            interval_mins = config.CHECK_INTERVAL_MINUTES

        interval_seconds = max(60, interval_mins * 60)
        logger.debug(f"Worker sleeping for {interval_mins} minutes...")
        
        # Sleep in short slices so process can exit cleanly
        for _ in range(interval_seconds // 5):
            time.sleep(5)

        try:
            monitor_agent.run_check_cycle()
        except Exception as e:
            logger.error(f"Error in scheduled monitoring cycle: {e}")

def main():
    logger.info("Initializing ODOCUST Academic Monitoring Agent...")

    # 1. Database
    database = Database(config.DATABASE_PATH)
    logger.info(f"Database initialized at {config.DATABASE_PATH}")

    # 2. Authentication
    auth = OdoCustAuth(
        base_url=config.ODOCUST_BASE_URL,
        username=config.ODOCUST_USERNAME,
        password=config.ODOCUST_PASSWORD,
        session_id=config.ODOCUST_SESSION_ID
    )

    # 3. Extractor
    extractor = OdoCustExtractor(base_url=config.ODOCUST_BASE_URL)

    # 4. WhatsApp Notifier
    notifier = get_whatsapp_notifier(
        provider=config.WHATSAPP_PROVIDER,
        twilio_account_sid=config.TWILIO_ACCOUNT_SID,
        twilio_auth_token=config.TWILIO_AUTH_TOKEN,
        twilio_whatsapp_from=config.TWILIO_WHATSAPP_FROM,
        callmebot_api_key=config.CALLMEBOT_API_KEY,
        callmebot_phone=config.CALLMEBOT_PHONE or config.WHATSAPP_TO_NUMBER,
        greenapi_instance_id=config.GREENAPI_INSTANCE_ID,
        greenapi_api_token=config.GREENAPI_API_TOKEN,
        telegram_bot_token=config.TELEGRAM_BOT_TOKEN,
        telegram_chat_id=config.TELEGRAM_CHAT_ID or config.WHATSAPP_TO_NUMBER,
        telegram_username=config.TELEGRAM_USERNAME
    )
    logger.info(f"WhatsApp provider initialized: {config.WHATSAPP_PROVIDER}")

    # 5. Monitor Agent
    dashboard_url = f"http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}"
    monitor_agent = AcademicMonitorAgent(
        auth=auth,
        db=database,
        extractor=extractor,
        notifier=notifier,
        whatsapp_to_number=config.WHATSAPP_TO_NUMBER,
        dashboard_url=dashboard_url
    )

    # 6. Start Background Monitor Thread
    worker_thread = threading.Thread(
        target=run_scheduler_loop,
        args=(monitor_agent, database),
        daemon=True,
        name="OdoCustWorkerThread"
    )
    worker_thread.start()

    # 7. Start Dashboard Web Application
    app = create_dashboard_app(database=database, monitor_agent=monitor_agent)
    logger.info(f"Starting Web Dashboard at {dashboard_url}")
    uvicorn.run(app, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, log_level="warning")

if __name__ == "__main__":
    main()
