import os
import requests
from logging_utils import log


class TwitchTokenManager:
    """
    Manages Twitch OAuth tokens with automatic refresh capability.
    """

    def __init__(self):
        self.client_id = os.getenv("BOT_CLIENT_ID")
        self.client_secret = os.getenv("BOT_CLIENT_SECRET")
        self.access_token = os.getenv("BOT_ACCESS_TOKEN")
        self.refresh_token = os.getenv("BOT_REFRESH_TOKEN")
        self._env_path = os.path.join(os.path.dirname(__file__), ".env")

    def get_token(self) -> str:
        """Returns current access token."""
        return self.access_token

    def get_client_id(self) -> str:
        """Returns client ID."""
        return self.client_id

    def refresh(self) -> bool:
        """
        Refreshes the access token using the refresh token.
        Returns True on success, False on failure.
        """
        if not self.refresh_token:
            log("❌ Brak refresh_token - nie można odświeżyć tokena", True, "error")
            return False

        if not self.client_secret:
            log("❌ Brak BOT_CLIENT_SECRET w .env - nie można odświeżyć tokena", True, "error")
            return False

        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        try:
            response = requests.post(url, data=data)

            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens["access_token"]
                # Twitch may return a new refresh token
                if "refresh_token" in tokens:
                    self.refresh_token = tokens["refresh_token"]
                self._update_env_file()
                log("🔄 Token odświeżony pomyślnie", True)
                return True
            else:
                log(f"❌ Błąd odświeżania tokena: {response.status_code} {response.text}", True, "error")
                return False

        except Exception as e:
            log(f"❌ Wyjątek podczas odświeżania tokena: {e}", True, "error")
            return False

    def _update_env_file(self):
        """Updates .env file with new tokens."""
        try:
            with open(self._env_path, "r") as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                if line.startswith("BOT_ACCESS_TOKEN="):
                    new_lines.append(f'BOT_ACCESS_TOKEN="{self.access_token}"\n')
                elif line.startswith("BOT_REFRESH_TOKEN="):
                    new_lines.append(f'BOT_REFRESH_TOKEN="{self.refresh_token}"\n')
                else:
                    new_lines.append(line)

            with open(self._env_path, "w") as f:
                f.writelines(new_lines)

            log("💾 Zapisano nowe tokeny do .env", True)

        except Exception as e:
            log(f"⚠️ Nie udało się zapisać tokenów do .env: {e}", True, "warning")


# Global instance
_token_manager = None


def get_token_manager() -> TwitchTokenManager:
    """Returns singleton instance of TwitchTokenManager."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TwitchTokenManager()
    return _token_manager
