import requests
import time

OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3"


class OllamaLlama3Client:
    """
    Client Ollama dédié aux tests avec Llama3, séparé de OllamaClient (qwen2.5)
    pour permettre de comparer les deux modèles locaux sans interférence.
    """

    def __init__(self, model=OLLAMA_MODEL, api_url=OLLAMA_API_URL):
        self.model = model
        self.api_url = api_url

    def is_available(self):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return self.model in models or any(self.model in m for m in models)
        except Exception:
            return False

    def call(self, system_prompt, user_message, temperature=0.2):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False,
            "options": {"temperature": temperature}
        }
        start = time.time()
        response = requests.post(self.api_url, json=payload, timeout=120)
        elapsed = time.time() - start
        response.raise_for_status()
        answer = response.json()["message"]["content"]
        return answer, elapsed