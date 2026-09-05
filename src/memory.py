from collections import deque
from datetime import datetime


class ConversationMemory:
    """
    Mémoire courte (short-term memory) : garde les N derniers échanges
    (question + réponse) d'une session utilisateur, pour permettre les
    questions de suivi sans faire grossir le prompt indéfiniment.

    Chaque session (ex: un chat_id Telegram, ou un identifiant de session
    web) a sa propre mémoire indépendante, stockée en mémoire (dict Python) —
    pas de persistance disque ici, volontairement : c'est de la mémoire
    "de travail" pour la session en cours, pas un historique permanent.
    """

    def __init__(self, max_turns=5):
        """max_turns : nombre d'échanges (Q+R) conservés par session"""
        self.max_turns = max_turns
        self.sessions = {}  # session_id -> deque de tours

    def add_turn(self, session_id, question, answer):
        """Ajoute un échange à la mémoire d'une session, en respectant la limite"""
        if session_id not in self.sessions:
            self.sessions[session_id] = deque(maxlen=self.max_turns)

        self.sessions[session_id].append({
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })

    def get_history(self, session_id):
        """Retourne l'historique d'une session (liste vide si aucune session)"""
        return list(self.sessions.get(session_id, []))

    def format_history_for_prompt(self, session_id):
        history = self.get_history(session_id)
        if not history:
            return ""

        lines = ["=== HISTORIQUE DE LA CONVERSATION (contexte uniquement, "
                "ne contient AUCUNE réponse valable pour la nouvelle question) ==="]
        for turn in history:
            lines.append(f"Q: {turn['question']}")
            lines.append(f"R: {turn['answer']}")
        lines.append("=== FIN DE L'HISTORIQUE ===")
        lines.append("")
        lines.append("Les réponses ci-dessus ne doivent JAMAIS être recopiées ou "
                    "réutilisées pour répondre à la nouvelle question ci-dessous, "
                    "même si le sujet semble proche. Utilise l'historique "
                    "UNIQUEMENT pour comprendre le contexte d'une question de suivi "
                    "(ex: 'et pour la 2ème année ?').")
        return "\n".join(lines)

    def clear_session(self, session_id):
        """Vide la mémoire d'une session (ex: commande /reset)"""
        if session_id in self.sessions:
            del self.sessions[session_id]