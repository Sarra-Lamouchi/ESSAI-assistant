import os
import requests
from memory import ConversationMemory
from prompt_builder import build_prompt
from llm_keys import GroqKeyRotator  

CEREBRAS_API_URL = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_MODEL = "openai/gpt-oss-120b"


class RAGGenerator:
    """
    Orchestration complète : reçoit une question + les chunks déjà récupérés
    par le pipeline retrieval (hybrid_search + rerank_with_fallback),
    construit le prompt avec mémoire courte, appelle le LLM (Cerebras)
    avec rotation/failover de clés, et retourne la réponse.
    """

    def __init__(self, max_memory_turns=5):
        
        self.key_rotator = GroqKeyRotator()
        self.memory = ConversationMemory(max_turns=max_memory_turns)

    def _call_cerebras(self, system_prompt, user_message, api_key, temperature=0.2):
        """Appel brut à l'API Cerebras avec une clé donnée"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": CEREBRAS_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature
        }
        response = requests.post(CEREBRAS_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _call_with_failover(self, system_prompt, user_message):
        """
        Essaie d'appeler l'API avec la clé courante ; en cas d'échec
        (rate limit, erreur réseau...), bascule automatiquement sur les
        clés suivantes jusqu'à succès ou épuisement de toutes les clés.
        """
        start_key = self.key_rotator.get_next_key()
        keys_to_try = self.key_rotator.get_all_keys_from(start_key)

        last_error = None
        for key in keys_to_try:
            try:
                return self._call_cerebras(system_prompt, user_message, key)
            except Exception as e:
                last_error = e
                print(f"⚠️ Échec avec une clé (essai suivant) : {e}")
                continue

        raise RuntimeError(f"Toutes les clés ont échoué. Dernière erreur : {last_error}")

    def generate(self, session_id, question, retrieved_chunks):
        """
        Point d'entrée principal : construit le prompt (avec mémoire courte),
        appelle le LLM, sauvegarde l'échange en mémoire, retourne la réponse.
        """
        conversation_history = self.memory.format_history_for_prompt(session_id)
        system_prompt, user_message = build_prompt(question, retrieved_chunks, conversation_history)

        answer = self._call_with_failover(system_prompt, user_message)

        self.memory.add_turn(session_id, question, answer)
        return answer

    def reset_session(self, session_id):
        """Efface la mémoire courte d'une session (ex: commande /reset)"""
        self.memory.clear_session(session_id)