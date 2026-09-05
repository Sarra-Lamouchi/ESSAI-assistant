import re
import random
from rapidfuzz import fuzz

# ============================================================
# DÉTECTION DES SALUTATIONS / SMALL TALK =
# ============================================================

GREETING_PATTERNS = {
    "salutation": [
        "salut", "bonjour", "bonsoir", "coucou", "hello", "hi", "hey",
        "yo", "slt", "bjr", "cc", "bsr", "salem", "salemalikom",
        "asalemalikom", "salam", "bonjr", "bonjrr",
    ],
    "au_revoir": [
        "au revoir", "bye", "à plus", "a plus", "salut à toi", "bonne journée",
        "bonne soirée", "bonne nuit", "à bientôt", "a bientot", "à demain",
        "a demain", "ciao", "tchao", "besslama", "beslama",
    ],
    "remerciement": [
        "merci", "thanks", "thx", "merci beaucoup", "je te remercie",
        "mercii", "merssi", "chokran", "yezik",
    ],
    "comment_ca_va": [
        "ça va", "ca va", "comment vas tu", "comment vas-tu", "how are you",
        "comment tu vas", "cv", "sava", "labes", "chnowa 7walek",
    ],
    "identite": [
        "qui es tu", "qui es-tu", "t'es qui", "tu es qui", "c'est quoi ton nom",
        "comment tu t'appelles", "que peux tu faire", "que peux-tu faire",
        "tu fais quoi", "tu sers a quoi", "tu peux m'aider avec quoi",
    ],
}

GREETING_RESPONSES = {
    "salutation": [
        "Bonjour ! Je suis l'assistant de l'ESSAI. Pose-moi une question sur les inscriptions, le PFE, le PFA, les clubs, la bibliothèque, etc.",
        "Salut ! Comment puis-je t'aider concernant l'ESSAI aujourd'hui ?",
    ],
    "au_revoir": [
        "Au revoir ! N'hésite pas à revenir si tu as d'autres questions sur l'ESSAI.",
        "À bientôt !",
    ],
    "remerciement": [
        "Avec plaisir ! N'hésite pas si tu as d'autres questions.",
        "De rien ! Je suis là si tu as besoin d'autre chose.",
    ],
    "comment_ca_va": [
        "Je vais bien, merci ! Je suis prêt à répondre à tes questions sur l'ESSAI — qu'est-ce que tu veux savoir ?",
    ],
    "identite": [
        "Je suis l'assistant virtuel de l'ESSAI. Je réponds aux questions sur les inscriptions, le PFE, le PFA, les clubs, le règlement intérieur, la bibliothèque, et bien plus — pose-moi une question !",
    ],
}

# Seuil de similarité fuzzy (0-100). En dessous, on considère que ce n'est
# pas une correspondance fiable — évite les faux positifs sur des mots
# qui ressemblent vaguement mais n'ont rien à voir.
FUZZY_THRESHOLD = 80

# Nombre max de mots dans le message pour être considéré comme small talk.
# Au-delà, même si un mot de salutation est détecté, on laisse passer au RAG
# (ex: "bonjour, c'est quand les inscriptions ?" doit déclencher le RAG).
MAX_WORDS_FOR_GREETING = 5


def _fuzzy_match_word(word, patterns, threshold=FUZZY_THRESHOLD):
    """
    Compare un mot à une liste de patterns avec tolérance aux fautes de
    frappe. Retourne True si le meilleur score dépasse le seuil.
    """
    for pattern in patterns:
        # Si le pattern est une expression multi-mots (ex: "au revoir"),
        # on la compare au message entier ailleurs, pas mot à mot ici.
        if " " in pattern:
            continue
        score = fuzz.ratio(word, pattern)
        if score >= threshold:
            return True
    return False


def detect_greeting(message):
    """
    Détecte si le message est du small talk (salutation, remerciement,
    au revoir, question d'identité) plutôt qu'une vraie question RAG.

    Logique :
    1. Nettoie le message (ponctuation, casse)
    2. Si trop long (> MAX_WORDS_FOR_GREETING mots) → pas du small talk,
       même si un mot de salutation apparaît dedans
    3. Cherche une correspondance EXACTE d'abord (rapide)
    4. Sinon, cherche une correspondance FUZZY (tolère les fautes de frappe)

    Retourne la catégorie détectée, ou None si c'est une vraie question.
    """
    cleaned = message.lower().strip()
    cleaned = re.sub(r"[!?.,;:]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    words = cleaned.split()
    word_count = len(words)

    # Message trop long → laisse passer au RAG, même s'il contient "bonjour"
    if word_count == 0 or word_count > MAX_WORDS_FOR_GREETING:
        return None

    # --- 1. Correspondance exacte sur le message entier ou les patterns multi-mots ---
    for category, patterns in GREETING_PATTERNS.items():
        for pattern in patterns:
            if cleaned == pattern or cleaned.startswith(pattern + " "):
                return category

    # --- 2. Fuzzy matching mot par mot (tolère les fautes de frappe) ---
    # Seulement si le message est court (1-2 mots) — évite les faux positifs
    # sur des phrases plus longues où un mot ressemble par hasard à une salutation.
    if word_count <= 2:
        for category, patterns in GREETING_PATTERNS.items():
            for word in words:
                if _fuzzy_match_word(word, patterns):
                    return category

    # --- 3. Fuzzy matching sur le message entier pour les patterns multi-mots ---
    if word_count <= MAX_WORDS_FOR_GREETING:
        for category, patterns in GREETING_PATTERNS.items():
            for pattern in patterns:
                if " " in pattern:
                    score = fuzz.ratio(cleaned, pattern)
                    if score >= FUZZY_THRESHOLD:
                        return category

    return None


def get_greeting_response(category):
    responses = GREETING_RESPONSES.get(category, GREETING_RESPONSES["salutation"])
    return random.choice(responses)