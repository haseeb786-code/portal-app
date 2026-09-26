import abc
import logging
import urllib.parse
from typing import Optional
import requests

logger = logging.getLogger("odocust.whatsapp")

class BaseWhatsAppNotifier(abc.ABC):
    @abc.abstractmethod
    def send_message(self, to_number: str, message: str) -> bool:
        """Sends a WhatsApp message to the specified recipient number."""
        pass

class ConsoleLogNotifier(BaseWhatsAppNotifier):
    """
    Fallback and local testing notifier. Logs notifications to stdout and database without external APIs.
    """
    def send_message(self, to_number: str, message: str) -> bool:
        separator = "=" * 50
        print(f"\n{separator}\n📱 [WHATSAPP DISPATCH -> {to_number or 'LOCAL'}]:\n{message}\n{separator}\n")
        logger.info(f"Simulated WhatsApp message dispatched to {to_number}")
        return True

class TwilioWhatsAppNotifier(BaseWhatsAppNotifier):
    """
    Official Twilio WhatsApp API.
    Zero risk of account ban. Requires Twilio Account SID and Auth Token.
    Supports Twilio Sandbox for personal testing.
    """
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
        self.endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    def send_message(self, to_number: str, message: str) -> bool:
        if not self.account_sid or not self.auth_token:
            logger.error("Twilio credentials missing.")
            return False

        formatted_to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
        try:
            res = requests.post(
                self.endpoint,
                auth=(self.account_sid, self.auth_token),
                data={
                    "From": self.from_number,
                    "To": formatted_to,
                    "Body": message
                },
                timeout=15
            )
            if res.status_code in (200, 201):
                logger.info(f"Twilio WhatsApp sent successfully: SID {res.json().get('sid')}")
                return True
            else:
                logger.error(f"Twilio error ({res.status_code}): {res.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Twilio WhatsApp message: {e}")
            return False

class CallMeBotWhatsAppNotifier(BaseWhatsAppNotifier):
    """
    CallMeBot API for personal WhatsApp.
    100% Free, no business account required.
    User gets API key by sending a WhatsApp message to CallMeBot.
    API: GET/POST https://api.callmebot.com/whatsapp.php?phone=[phone]&text=[text]&apikey=[apikey]
    """
    def __init__(self, api_key: str, default_phone: str = ""):
        self.api_key = api_key
        self.default_phone = default_phone

    def send_message(self, to_number: str, message: str) -> bool:
        phone = (to_number or self.default_phone).replace("+", "").replace(" ", "").replace("-", "")
        if not phone or not self.api_key:
            logger.error("CallMeBot phone or API key missing.")
            return False

        encoded_text = urllib.parse.quote_plus(message)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={self.api_key}"
        try:
            res = requests.get(url, timeout=20)
            if res.status_code == 200 and "success" in res.text.lower():
                logger.info("CallMeBot message sent successfully.")
                return True
            elif res.status_code == 200:
                # CallMeBot sometimes returns text like "Message queued"
                logger.info(f"CallMeBot response: {res.text}")
                return True
            else:
                logger.error(f"CallMeBot failed with status {res.status_code}: {res.text}")
                return False
        except Exception as e:
            logger.error(f"CallMeBot dispatch exception: {e}")
            return False

class GreenApiWhatsAppNotifier(BaseWhatsAppNotifier):
    """
    Green-API WhatsApp integration.
    Supports personal and business WhatsApp via cloud gateway.
    """
    def __init__(self, instance_id: str, api_token: str):
        self.instance_id = instance_id
        self.api_token = api_token

    def send_message(self, to_number: str, message: str) -> bool:
        if not self.instance_id or not self.api_token:
            logger.error("Green-API instance_id or api_token missing.")
            return False

        clean_number = to_number.replace("+", "").replace(" ", "").replace("-", "")
        chat_id = f"{clean_number}@c.us"
        url = f"https://api.green-api.com/waInstance{self.instance_id}/sendMessage/{self.api_token}"

        try:
            payload = {"chatId": chat_id, "message": message}
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                logger.info("Green-API message sent.")
                return True
            else:
                logger.error(f"Green-API error ({res.status_code}): {res.text}")
                return False
        except Exception as e:
            logger.error(f"Green-API exception: {e}")
            return False

class TelegramNotifier(BaseWhatsAppNotifier):
    """
    Direct Telegram Bot notifier or CallMeBot Telegram.
    100% Free, zero account limit, instant delivery.
    """
    def __init__(self, bot_token: str = "", chat_id: str = "", callmebot_username: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.callmebot_username = callmebot_username

    def send_message(self, to_number: str, message: str) -> bool:
        # If standard Telegram Bot token & chat_id provided
        if self.bot_token and (to_number or self.chat_id):
            cid = to_number or self.chat_id
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            try:
                res = requests.post(url, json={"chat_id": cid, "text": message, "parse_mode": "Markdown"}, timeout=15)
                return res.status_code == 200
            except Exception as e:
                logger.error(f"Telegram Bot error: {e}")
                return False

        # If CallMeBot Telegram user provided
        user = (to_number or self.callmebot_username).lstrip("@")
        if user:
            encoded_text = urllib.parse.quote_plus(message)
            url = f"https://api.callmebot.com/text.php?user=@{user}&text={encoded_text}"
            try:
                res = requests.get(url, timeout=15)
                return res.status_code == 200
            except Exception as e:
                logger.error(f"CallMeBot Telegram error: {e}")
                return False

        logger.error("No valid Telegram credentials provided.")
        return False

def get_whatsapp_notifier(provider: str, **kwargs) -> BaseWhatsAppNotifier:
    """
    Factory function to instantiate the selected notification provider.
    """
    p = provider.lower().strip()
    if p == "twilio":
        return TwilioWhatsAppNotifier(
            account_sid=kwargs.get("twilio_account_sid", ""),
            auth_token=kwargs.get("twilio_auth_token", ""),
            from_number=kwargs.get("twilio_whatsapp_from", "whatsapp:+14155238886")
        )
    elif p in ("callmebot", "whatsapp"):
        return CallMeBotWhatsAppNotifier(
            api_key=kwargs.get("callmebot_api_key", ""),
            default_phone=kwargs.get("callmebot_phone", "")
        )
    elif p in ("telegram", "telegram_callmebot"):
        return TelegramNotifier(
            bot_token=kwargs.get("telegram_bot_token", ""),
            chat_id=kwargs.get("telegram_chat_id", ""),
            callmebot_username=kwargs.get("telegram_username", "")
        )
    elif p == "greenapi":
        return GreenApiWhatsAppNotifier(
            instance_id=kwargs.get("greenapi_instance_id", ""),
            api_token=kwargs.get("greenapi_api_token", "")
        )
    else:
        return ConsoleLogNotifier()
