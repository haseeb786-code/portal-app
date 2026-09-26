import time
import os
import re
import logging
from typing import Optional, Dict
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("odocust.auto_auth")

class AutoLoginManager:
    def __init__(self, base_url: str = "https://tasjeel.cust.edu.pk"):
        self.base_url = base_url.rstrip("/")

    def perform_microsoft_login(self, email: str, password: str, headless: bool = True) -> Optional[str]:
        """
        Automates CUST Microsoft Single Sign-On (SSO) login flow.
        Extracts and returns the fresh 'session_id' cookie.
        """
        logger.info(f"Starting automated Microsoft login for {email} (headless={headless})...")
        
        with sync_playwright() as p:
            # Prefer Chrome, fallback to Edge
            browser = None
            for ch in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch(channel=ch, headless=headless)
                    logger.info(f"Launched browser using {ch}")
                    break
                except Exception as e:
                    logger.debug(f"Could not launch {ch}: {e}")

            if not browser:
                # Default chromium fallback
                browser = p.chromium.launch(headless=headless)

            context = browser.new_context()
            page = context.new_page()

            try:
                # 1. Navigate to CUST Student Dashboard
                dashboard_url = f"{self.base_url}/student/dashboard"
                logger.info(f"Navigating to {dashboard_url}...")
                page.goto(dashboard_url, timeout=45000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

                # If already logged in, extract cookie immediately
                cookies = context.cookies()
                for c in cookies:
                    if c["name"] == "session_id" and "tasjeel" in c.get("domain", ""):
                        if "dashboard" in page.url and "web/login" not in page.url:
                            logger.info("Already logged in! Returning active session.")
                            browser.close()
                            return c["value"]

                # 2. If on login page, initiate Microsoft SSO
                current_url = page.url
                logger.info(f"Current URL: {current_url}")

                if "microsoft" not in current_url:
                    # Look for Microsoft signin button
                    ms_btn = page.query_selector("a[href*='microsoft'], a[href*='oauth']")
                    if ms_btn:
                        logger.info("Clicking 'Sign in with Microsoft' button...")
                        ms_btn.click()
                    else:
                        logger.info("Directly navigating to Microsoft SSO authorization URL...")
                        page.goto(f"{self.base_url}/auth_oauth/microsoft/signin", timeout=30000)

                # Wait for Microsoft login page
                logger.info("Waiting for Microsoft login page...")
                page.wait_for_selector("input[type='email'], input[name='loginfmt'], #i0116", timeout=30000)
                logger.info(f"Reached Microsoft login page: {page.title()}")

                # 3. Enter Email
                email_input = page.query_selector("input[type='email'], input[name='loginfmt'], #i0116")
                if email_input:
                    logger.info(f"Filling email: {email}")
                    email_input.fill(email)
                    time.sleep(0.5)

                    # Click Next
                    next_btn = page.query_selector("#idSIButton9, input[type='submit'], button[type='submit']")
                    if next_btn:
                        next_btn.click()
                        time.sleep(2)

                # 4. Enter Password
                logger.info("Waiting for password input...")
                page.wait_for_selector("input[type='password'], input[name='passwd'], #i0118", timeout=30000)
                pass_input = page.query_selector("input[type='password'], input[name='passwd'], #i0118")
                if pass_input:
                    logger.info("Filling password...")
                    pass_input.fill(password)
                    time.sleep(0.5)

                    # Click Sign In
                    signin_btn = page.query_selector("#idSIButton9, input[type='submit'], button[type='submit']")
                    if signin_btn:
                        signin_btn.click()
                        time.sleep(3)

                # 5. Handle 'Stay signed in?' (KMSI prompt) if it appears
                try:
                    kmsi_btn = page.wait_for_selector("#idSIButton9, input[value='Yes'], button:has-text('Yes')", timeout=7000)
                    if kmsi_btn:
                        logger.info("Accepting 'Stay signed in' prompt...")
                        kmsi_btn.click()
                        time.sleep(3)
                except Exception:
                    logger.debug("No 'Stay signed in' prompt displayed.")

                # 6. Wait for redirect back to CUST portal
                logger.info("Waiting for redirect back to CUST portal...")
                page.wait_for_url(lambda u: "tasjeel.cust.edu.pk" in u or "odoo.cust.edu.pk" in u, timeout=45000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

                logger.info(f"Final URL reached: {page.url}")

                # 7. Extract cookies
                all_cookies = context.cookies()
                session_id = None
                for c in all_cookies:
                    if c["name"] == "session_id":
                        session_id = c["value"]
                        logger.info(f"Found session_id cookie: {session_id[:8]}... (Domain: {c.get('domain')})")
                        break

                browser.close()
                return session_id

            except Exception as e:
                logger.error(f"Error during automated Microsoft login: {e}")
                try:
                    # Take error screenshot for debugging
                    page.screenshot(path="login_error.png")
                    logger.info("Saved error screenshot to login_error.png")
                except Exception:
                    pass
                browser.close()
                return None

if __name__ == "__main__":
    import config
    manager = AutoLoginManager(config.ODOCUST_BASE_URL)
    email = "bse233195@cust.pk"
    pwd = config.ODOCUST_PASSWORD
    sess = manager.perform_microsoft_login(email, pwd, headless=True)
    print("Result session_id:", sess)
