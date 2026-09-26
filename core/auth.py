import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, Dict
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.auto_auth import AutoLoginManager

logger = logging.getLogger("odocust.auth")

class AuthenticationError(Exception):
    pass

class OdoCustAuth:
    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        email: str = "",
        session_id: str = "",
        session_cache_file: str = ".session_cache.json"
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.email = email or (f"{username}@cust.pk" if username else "")
        self.manual_session_id = session_id
        self.cache_file = Path(session_cache_file)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get_authenticated_session(self) -> requests.Session:
        """
        Returns a verified active session. Re-authenticates if expired.
        """
        if self.is_session_valid():
            logger.debug("Existing session is valid.")
            return self.session

        logger.info("Session invalid or expired. Attempting authentication...")
        if self.manual_session_id:
            logger.info("Applying manual session_id...")
            for dom in ["tasjeel.cust.edu.pk", "odoo.cust.edu.pk"]:
                self.session.cookies.set("session_id", self.manual_session_id, domain=dom)
            if self.is_session_valid():
                logger.info("Manual session_id verified successfully.")
                self._save_session_cache()
                return self.session
            else:
                logger.warning("Provided manual session_id is expired or invalid.")

        # 1. Attempt automated Microsoft SSO login (Zero-touch)
        email = self.email or f"{self.username}@cust.pk"
        if email and self.password:
            logger.info(f"Triggering automated Microsoft SSO login for {email}...")
            try:
                auto_mgr = AutoLoginManager(self.base_url)
                new_session_id = auto_mgr.perform_microsoft_login(email, self.password, headless=True)
                if new_session_id:
                    self.manual_session_id = new_session_id
                    for dom in ["tasjeel.cust.edu.pk", "odoo.cust.edu.pk"]:
                        self.session.cookies.set("session_id", new_session_id, domain=dom)
                    if self.is_session_valid():
                        logger.info("Automated Microsoft SSO login succeeded! Session refreshed.")
                        self._save_session_cache()
                        self._update_env_session_id(new_session_id)
                        return self.session
            except Exception as e:
                logger.warning(f"Automated Microsoft SSO attempt failed: {e}")

        # 2. Fallback to Odoo standard credential login
        if self.username and self.password:
            self._login_with_credentials()
            if self.is_session_valid():
                logger.info(f"Successfully authenticated as {self.username}")
                self._save_session_cache()
                return self.session
            else:
                raise AuthenticationError(f"Login failed for user '{self.username}'. Credentials rejected by ODOCUST.")

        raise AuthenticationError("No valid session or credentials provided. Please set ODOCUST_USERNAME & ODOCUST_PASSWORD or ODOCUST_SESSION_ID.")

    def keep_alive_ping(self) -> bool:
        """
        Sends a lightweight request to the portal to refresh the idle session timeout.
        """
        try:
            res = self.session.get(f"{self.base_url}/student/dashboard", timeout=12, verify=False, allow_redirects=False)
            return res.status_code == 200
        except Exception:
            return False

    def _update_env_session_id(self, new_session_id: str):
        try:
            env_path = Path(".env")
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")
                updated = re.sub(r'ODOCUST_SESSION_ID=.*', f'ODOCUST_SESSION_ID={new_session_id}', content)
                env_path.write_text(updated, encoding="utf-8")
                logger.info("Updated .env with fresh ODOCUST_SESSION_ID.")
        except Exception as e:
            logger.warning(f"Could not update .env file: {e}")

    def is_session_valid(self) -> bool:
        """
        Checks if current session can access /student/dashboard without redirection to login.
        """
        # Load cached session if session cookie isn't in memory yet
        if "session_id" not in self.session.cookies:
            self._load_session_cache()

        if "session_id" not in self.session.cookies:
            return False

        try:
            dashboard_url = f"{self.base_url}/student/dashboard"
            res = self.session.get(dashboard_url, timeout=12, verify=False, allow_redirects=False)
            
            # If valid, student dashboard returns 200 OK.
            # If expired/invalid, Odoo returns 302/303 redirect to /web/login?redirect=...
            if res.status_code == 200 and "/web/login" not in res.url:
                # Extra check: ensure not login page HTML
                if "name=\"csrf_token\"" in res.text and "Login Directly" in res.text:
                    return False
                return True
            return False
        except Exception as e:
            logger.warning(f"Error checking session validity: {e}")
            return False

    def _login_with_credentials(self):
        """
        Executes standard Odoo 15 web login flow:
        1. GET /web/login to extract csrf_token
        2. POST /web/login with credentials
        """
        login_url = f"{self.base_url}/web/login"
        try:
            get_res = self.session.get(login_url, timeout=15, verify=False)
            csrf_match = re.search(r'name=["\']csrf_token["\'] value=["\']([^"\']+)["\']', get_res.text)
            if not csrf_match:
                raise AuthenticationError("Failed to extract CSRF token from ODOCUST login page.")
            
            csrf_token = csrf_match.group(1)
            payload = {
                "csrf_token": csrf_token,
                "login": self.username,
                "password": self.password,
                "redirect": "/student/dashboard"
            }

            post_res = self.session.post(login_url, data=payload, timeout=20, verify=False, allow_redirects=True)
            
            # Check for success
            if post_res.status_code == 200:
                if "/student/dashboard" in post_res.url or "student" in post_res.url:
                    return
                # Check if still on login page with error
                if "Login Directly" in post_res.text:
                    raise AuthenticationError("ODOCUST rejected the login credentials. Please check your username and password.")

        except requests.RequestException as e:
            raise AuthenticationError(f"Network error connecting to ODOCUST portal: {e}")

    def _get_cookie_domain(self) -> str:
        domain = self.base_url.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        return domain

    def _save_session_cache(self):
        try:
            cookies = self.session.cookies.get_dict()
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            logger.debug(f"Saved session cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to cache session cookies: {e}")

    def _load_session_cache(self):
        if not self.cache_file.exists():
            return
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                for k, v in cookies.items():
                    self.session.cookies.set(k, v, domain=self._get_cookie_domain())
            logger.debug("Loaded session cookies from cache.")
        except Exception as e:
            logger.warning(f"Failed to load session cache: {e}")
