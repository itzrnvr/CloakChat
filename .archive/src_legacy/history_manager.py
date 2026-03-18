from typing import List, Dict

class HistoryManager:
    def __init__(self):
        # History visible to the user (contains real PII)
        self.user_history: List[Dict[str, str]] = []
        # History sent to the cloud (contains placeholders)
        self.cloud_history: List[Dict[str, str]] = []

    def add_message(self, role: str, original_content: str, sanitized_content: str):
        """
        Adds a message to both histories.
        role: "user" or "assistant" (or "model")
        """
        self.user_history.append({"role": role, "content": original_content})
        self.cloud_history.append({"role": role, "content": sanitized_content})

    def get_cloud_history(self) -> List[Dict[str, str]]:
        return self.cloud_history

    def get_user_history(self) -> List[Dict[str, str]]:
        return self.user_history

    def clear(self):
        self.user_history = []
        self.cloud_history = []
