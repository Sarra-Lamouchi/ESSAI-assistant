import re
from rapidfuzz import fuzz

CONVENTION_LINKS = {
    "insertion": {
        "url": "http://www.essai.rnu.tn/documents-utiles/conventions/stage-insertion/971-convention-insertion-2020/file",
        "label": "Convention de stage d'insertion / d'initiation (1ère année)",
        "keywords": [
            "insertion", "initiation", "stage 1ere annee", "stage 1ère année",
            "stage premiere annee", "stage première année",
        ],
    },
    "ingenieur": {
        "url": "http://www.essai.rnu.tn/documents-utiles/conventions/stage-ingenieurs/986-convention-ingenieur-2020/file",
        "label": "Convention de stage d'ingénieur (2ème année)",
        "keywords": [
            "stage ingenieur", "stage ingénieur", "stage 2eme annee", "stage 2ème année",
            "stage deuxieme annee", "stage deuxième année",
        ],
    },
}

PFE_KEYWORDS = ["pfe", "fin d'etudes", "fin d'études", "projet de fin d'etudes", "projet de fin d'études"]

STAGE_TRIGGER_WORDS = ["stage", "convention", "conventions"]


def detect_convention_request(message):
    """
    Détecte si la question porte sur une convention de stage spécifique
    (insertion, ingénieur, ou PFE). Retourne la clé du type détecté
    ("insertion", "ingenieur", "pfe") ou None si aucune correspondance claire.
    """
    cleaned = message.lower().strip()
    cleaned = re.sub(r"[^\wàâäéèêëïîôöùûüç' ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    has_stage_context = any(w in cleaned for w in STAGE_TRIGGER_WORDS)
    if not has_stage_context:
        return None

    # PFE d'abord — priorité car pas de lien fixe à donner
    for kw in PFE_KEYWORDS:
        if kw in cleaned or fuzz.partial_ratio(kw, cleaned) >= 85:
            return "pfe"

    for key, data in CONVENTION_LINKS.items():
        for kw in data["keywords"]:
            if kw in cleaned or fuzz.partial_ratio(kw, cleaned) >= 85:
                return key

    return None


def get_convention_response(convention_type):
    if convention_type == "pfe":
        return ("La convention de PFE n'a pas de lien fixe à fournir ici — merci de la "
                 "consulter directement sur le site officiel de l'ESSAI, car elle peut être mise à jour.")

    data = CONVENTION_LINKS.get(convention_type)
    if not data:
        return None

    return f"Voici le lien vers la {data['label']} :\n{data['url']}"