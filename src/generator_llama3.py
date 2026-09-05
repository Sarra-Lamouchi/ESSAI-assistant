from memory import ConversationMemory
from prompt_builder import build_prompt
from local_llm_llama3 import OllamaLlama3Client

OLLAMA_MODEL = "llama3"


class RAGGeneratorLlama3:
    """
    Version du RAGGenerator dédiée aux tests avec Llama3 en local via Ollama.
    Structure identique à RAGGenerator (generator.py), seul le client LLM change.
    """

    def __init__(self, max_memory_turns=5, ollama_model=OLLAMA_MODEL):
        self.memory = ConversationMemory(max_turns=max_memory_turns)
        self.ollama_client = OllamaLlama3Client(model=ollama_model)
        if not self.ollama_client.is_available():
            print(f"⚠️ Attention : Ollama ne semble pas avoir le modèle '{ollama_model}' "
                  f"chargé, ou le serveur n'est pas lancé")

    def generate(self, session_id, question, retrieved_chunks):
        conversation_history = self.memory.format_history_for_prompt(session_id)
        system_prompt, user_message = build_prompt(question, retrieved_chunks, conversation_history)
        answer, elapsed = self.ollama_client.call(system_prompt, user_message)
        self.memory.add_turn(session_id, question, answer)
        return answer, elapsed

    def reset_session(self, session_id):
        self.memory.clear_session(session_id)