# tos_api.py
import time
import requests
from config import (
    TOS_CLIENT_ID,
    TOS_REFRESH_TOKEN,
    TOS_REDIRECT_URI,
    TOS_BASE_URL
)

class TOSAPI:
    def __init__(self):
        self.access_token = None
        self.expiration = 0

    def refresh_access_token(self):
        """
        Uses Schwab OAuth refresh token to get a new access token.
        """
        url = "https://api.schwabapi.com/v1/oauth/token"

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": TOS_REFRESH_TOKEN,
            "client_id": TOS_CLIENT_ID
        }

        print("Requesting new Schwab access token...")

        response = requests.post(url, data=payload)
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        data = response.json()

        self.access_token = data["access_token"]
        self.expiration = time.time() + data["expires_in"] - 30  # safety buffer

        print("New access token obtained.")

    def _ensure_token(self):
        if not self.access_token or time.time() > self.expiration:
            self.refresh_access_token()

    def get(self, endpoint, params=None):
        """
        Sends a GET request to Schwab Trader API.
        """
        self._ensure_token()

        url = f"{TOS_BASE_URL}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            raise Exception(f"Schwab API GET failed: {response.text}")

        return response.json()