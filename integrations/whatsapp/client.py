import os
import requests
import logging

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """Meta WhatsApp Cloud API Client with automated simulation mode."""

    def __init__(self, token=None, phone_number_id=None):
        self.token = token or os.environ.get('WHATSAPP_TOKEN', '')
        self.phone_number_id = phone_number_id or os.environ.get('WHATSAPP_PHONE_ID', '')
        self.api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"

    def send_text_message(self, to_phone, text):
        """Sends a text message to a WhatsApp number."""
        if not self.token or not self.phone_number_id:
            logger.info(f"[SIMULATED WHATSAPP OUTBOUND] To: {to_phone} | Message: {text}")
            return {"status": "simulated", "to": to_phone, "text": text}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to dispatch WhatsApp message: {e}")
            return {"error": str(e)}
