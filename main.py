import logging
import threading
import time
import time
import sys

# If running under pythonw.exe, sys.stdout and sys.stderr are None. Redirect them to log file.
if sys.stdout is None:
    try:
        sys.stdout = open("odocust_agent.log", "a", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open("odocust_agent.log", "a", encoding="utf-8")
    except Exception:
        pass

# Ensure UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn

import config
from core.database import Database
from core.auth import OdoCustAuth
from core.extractor import OdoCustExtractor
from notifier.whatsapp import get_whatsapp_notifier
from engine.monitor import AcademicMonitorAgent
from dashboard.app import create_dashboard_app

# Configure logging (safely handles pythonw.exe where sys.stdout is None)
handlers = [logging.FileHandler("odocust_agent.log", encoding="utf-8")]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers
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

def run_heartbeat_loop(auth: OdoCustAuth):
    """
    Sends a lightweight keep-alive ping every 20 minutes to keep portal session permanently alive.
    """
    logger.info("Session keep-alive heartbeat active (20-minute intervals).")
    while True:
        time.sleep(1200)  # 20 minutes
        try:
            ok = auth.keep_alive_ping()
            if ok:
                logger.debug("Session heartbeat ping OK: Portal session active.")
            else:
                logger.info("Session heartbeat detected expired session. Auto-refreshing via Microsoft SSO...")
                auth.get_authenticated_session()
        except Exception as e:
            logger.debug(f"Session heartbeat error: {e}")

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
        email=config.ODOCUST_EMAIL,
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

    # 7. Start Session Keep-Alive Heartbeat Thread
    heartbeat_thread = threading.Thread(
        target=run_heartbeat_loop,
        args=(auth,),
        daemon=True,
        name="SessionHeartbeatThread"
    )
    heartbeat_thread.start()

    # 7. Start Dashboard Web Application
    app = create_dashboard_app(database=database, monitor_agent=monitor_agent)
    logger.info(f"Starting Web Dashboard at {dashboard_url}")
    uvicorn.run(app, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, log_level="warning")

if __name__ == "__main__":
    main()
