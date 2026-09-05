import json
import os
import re


# ============================================================
# CHARGEMENT DES DOCUMENTS EXTRAITS
# ============================================================

EXTRACTOR_BY_FILE = {
    "communique_d_inscription_pdf.pdf": "docling",
}
DEFAULT_EXTRACTOR = "pymupdf"


def get_extractor_for_file(filename):
    return EXTRACTOR_BY_FILE.get(filename, DEFAULT_EXTRACTOR)


def load_final_text(filename, extractor=None, base_path="../data/processed/extracted_text"):
    if extractor is None:
        extractor = get_extractor_for_file(filename)
    json_path = os.path.join(base_path, extractor, filename.replace(".pdf", ".json"))
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    full_text = "\n\n".join(p["text"] for p in data["pages"])
    return {
        "filename": filename,
        "extractor_used": extractor,
        "text": full_text,
        "num_pages": len(data["pages"])
    }


# ============================================================
# TABLE DE DÉCISION
# ============================================================

CHUNKING_STRATEGY = {
    "Ateliers_statistique.pdf": "whole_page_detailed",
    "Note_PFE.pdf": "whole_page_detailed",
    "organisation_activitésclubs_ESSAI.pdf": "whole_page_detailed",
    "communique_d_inscription_pdf.pdf": "whole_page_detailed",

    "Charte_des_clubs.pdf": "subtitle",
    "FAQ_ESSAI.pdf": "subtitle",
    "Modalités_Admission_DoubleDiplome.pdf": "subtitle",
    "Règlement_Bib.pdf": "subtitle",
    "Règlement_Examen_ESSAI.pdf": "subtitle",
    "Guide_Etudiant.pdf": "subtitle",  
    "association_clubs.pdf": "subtitle",

    "Règlement_intérieur.pdf": "subtitle_numbered",
    "Convention_PFE_ESSAI.pdf": "subtitle_numbered",

    "Regime_etudes_ESSAI2022.pdf": "hybrid_articles_tables",
}


def get_strategy_for_file(filename):
    strategy = CHUNKING_STRATEGY.get(filename)
    if strategy is None:
        raise ValueError(f"Aucune stratégie de chunking définie pour : {filename}")
    return strategy


# ============================================================
# TITRE DÉRIVÉ DU NOM DE FICHIER (pour whole_page_detailed)
# ============================================================

FRIENDLY_TITLES = {
    "Ateliers_statistique.pdf": "Ateliers de statistique",
    "Note_PFE.pdf": "Note relative au PFE",
    "organisation_activitésclubs_ESSAI.pdf": "Organisation des activités des clubs ESSAI",
    "communique_d_inscription_pdf.pdf": "Communiqué d'inscription",
}


def filename_to_title(filename):
    if filename in FRIENDLY_TITLES:
        return FRIENDLY_TITLES[filename]
    name = filename.replace(".pdf", "")
    name = re.sub(r"[_\-]+", " ", name).strip()
    return name


# ============================================================
# EXTRACTION DE TITRE
# ============================================================

def extract_title(text, max_lines=2):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return " ".join(lines[:max_lines])


def extract_first_line(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[0] if lines else None

def strip_administrative_header(text):
    """
    Retire l'en-tête administratif générique (adresse, ministère, université,
    téléphone/fax) qui pollue le début de certains chunks whole_page —
    ce bloc répétitif dilue l'embedding sans apporter d'information distinctive.
    """
    header_patterns = [
        r"Adresse\s*:.*?(?:\n|$)",
        r"Tél\s*[:.].*?(?:\n|$)",
        r"Fax\s*[:.].*?(?:\n|$)",
        r"République\s+Tunisienne.*?(?:\*{3,}.*?){0,4}",
        r"Ministère\s+de\s+l.Enseignement\s+Supérieur.*?(?:\n|$)",
        r"Université\s+de\s+Carthage.*?(?:\n|$)",
        r"Ecole\s+Supérieure\s+de\s+la\s+Statistique.*?(?:\n|$)",
        r"Site\s+web\s*:.*?(?:\n|$)",
    ]
    cleaned = text
    for pattern in header_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

# ============================================================
# MÉTHODE 1 — page complète
# ============================================================

def chunk_whole_page_detailed(document):
    full_text = strip_administrative_header(document["text"].strip())  # ← modifié
    title = filename_to_title(document["filename"])
    return [{
        "text": full_text,
        "title": title,
        "subtitle": title,
        "page_number": 1,
        "total_pages": document.get("num_pages", 1),
    }]


# ============================================================
# MÉTHODE 2a — chunking par sous-titre LITTÉRAL
# ============================================================

SUBTITLE_MARKERS = {
    "Charte_des_clubs.pdf": [
        "Titre premier :",
        "Titre II :",
        "Titre III :",
        "Titre IV :",
    ],
    "FAQ_ESSAI.pdf": [
    "INSCRIPTIONS",
    "PFE ET STAGES",
    "PRATIQUE",
    "CARTES ÉTUDIANTES",
    "ÉTUDES",
    "PROGRAMME DE L'ESSAI",
    "OPTIONS EN 3ème ANNÉE",
    "ABSENCES",
    "EXAMENS",
    "L'ESSAI ET APRÈS",
    ],
    "Modalités_Admission_DoubleDiplome.pdf": [
        "Modalités de candidature",
        "Nombre de candidats retenus",
        "Dossier de candidature",
        "Sélection",
        "Financement",
        "Diplômes délivrés",
    ],
    "Règlement_Bib.pdf": [
        "DISPOSITIONS GENERALES",
        "ACCES",
        "CONSULTATION SUR PLACE",
        "PRET A DOMICILE",
        "RETARD ET PERTE",
        "DISCIPLINE",
        "AFFICHAGE ET APPLICATION DU REGLEMENT",
    ],
    "Règlement_Examen_ESSAI.pdf": [
        "Respect des listes/des places",
        "Pièces d'identité",
        "Portable",
        "Feuilles /documents",
        "Ecriture sur les tables",
        "Retard/départ/Sortie de la salle",
        "Respect de l'enseignant surveillant",
        "Remise des feuilles d'examen",
        "Fraude ou tentative de fraude",
    ],

    "Guide_Etudiant.pdf": [
        "1. Bibliothèque",
        "2. Études et Organisation pédagogique",
        "3. Double diplôme et opportunités",
        "4. Absences",
        "5. Examens et évaluation",
        "6. Crédits et progression",
        "7. Diplôme et documents administratifs",
        "8. Après l’ESSAI",
        "9. Informations générales",
    ],
    "association_clubs.pdf": [  
        "Association ASIA",
        "ESSAI Machine Learning Club",
        "Enactus ESSAI",
        "WAVY Club ESSAI",
    ],
}


def chunk_by_subtitle(text, markers):
    if not markers:
        raise ValueError("Aucun marqueur de sous-titre défini pour ce document.")

    pattern = "(" + "|".join(re.escape(m) for m in markers) + ")"
    parts = re.split(pattern, text)

    chunks = []
    preamble = parts[0].strip()
    if preamble:
        chunks.append({"subtitle": extract_first_line(preamble), "text": preamble})

    i = 1
    while i < len(parts):
        marker = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        chunk_text = (marker + content).strip()
        subtitle = extract_first_line(chunk_text)
        chunks.append({"subtitle": subtitle, "text": chunk_text})
        i += 2

    return chunks


# ============================================================
# MÉTHODE 2b — chunking par sous-titre NUMÉROTÉ (Article N)
# ============================================================

ARTICLE_PATTERN = re.compile(r'(Article\s+\d+\s*[\-–:]?\s*[^\n]*)')


def chunk_by_numbered_article(text):
    parts = ARTICLE_PATTERN.split(text)
    chunks = []
    preamble = parts[0].strip()
    if preamble:
        chunks.append({"subtitle": extract_first_line(preamble), "text": preamble})

    i = 1
    while i < len(parts):
        marker_line = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        chunk_text = (marker_line + "\n" + content).strip()
        chunks.append({"subtitle": marker_line, "text": chunk_text})
        i += 2

    return chunks


# ============================================================
# DÉTECTION DES CHUNKS DE TYPE TABLEAU
# ============================================================

def is_table_like_chunk(text, max_whitespace_ratio=0.4, min_word_length_avg=3):
    words = text.split()
    if not words:
        return True
    whitespace_ratio = text.count('\n') / max(len(text), 1)
    avg_word_len = sum(len(w) for w in words) / len(words)
    return whitespace_ratio > max_whitespace_ratio or avg_word_len < min_word_length_avg
# ============================================================
# MÉTHODE 5 — chunking HYBRIDE (articles + tableaux)
# ============================================================

def split_mixed_article_table(chunk_text, min_table_line_len=15):
    """
    Pour un chunk 'Article N' qui contient à la fois du texte légal ET un
    tableau, sépare les deux en deux sous-chunks distincts — le texte légal
    reste lisible pour l'embedding, le tableau est isolé (et peut être filtré
    ou traité séparément), au lieu de rester mélangés dans un seul chunk où
    le bruit tabulaire écrase le signal textuel.
    """
    lines = chunk_text.split("\n")
    text_lines, table_lines = [], []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if len(stripped) < min_table_line_len and stripped:
            in_table = True
        if in_table:
            table_lines.append(line)
        else:
            text_lines.append(line)

    text_part = "\n".join(text_lines).strip()
    table_part = "\n".join(table_lines).strip()
    return text_part, table_part


def chunk_hybrid_articles_tables(text):
    raw_chunks = chunk_by_numbered_article(text)
    final_chunks = []

    for c in raw_chunks:
        text_part, table_part = split_mixed_article_table(c["text"])
        if table_part and len(table_part) > 200:  # tableau substantiel détecté
            final_chunks.append({**c, "text": text_part, "is_table": False})
            final_chunks.append({**c, "text": table_part, "is_table": True,
                                   "subtitle": c["subtitle"] + " (tableau)"})
        else:
            c["is_table"] = is_table_like_chunk(c["text"])
            final_chunks.append(c)

    return final_chunks





# ============================================================
# ORCHESTRATION
# ============================================================

def chunk_document_custom(document, **kwargs):
    strategy = get_strategy_for_file(document["filename"])

    if strategy == "whole_page_detailed":
        raw_chunks = chunk_whole_page_detailed(document)

    elif strategy == "subtitle":
        markers = SUBTITLE_MARKERS.get(document["filename"], [])
        raw_chunks = chunk_by_subtitle(document["text"], markers)
        for c in raw_chunks:
            c["title"] = extract_title(document["text"])
            c["page_number"] = None
            c["total_pages"] = document.get("num_pages", 1)

    elif strategy == "subtitle_numbered":
        raw_chunks = chunk_by_numbered_article(document["text"])
        for c in raw_chunks:
            c["title"] = extract_title(document["text"])
            c["page_number"] = None
            c["total_pages"] = document.get("num_pages", 1)

    elif strategy == "hybrid_articles_tables":
        raw_chunks = chunk_hybrid_articles_tables(document["text"])
        for c in raw_chunks:
            c["title"] = filename_to_title(document["filename"])
            c["page_number"] = None
            c["total_pages"] = document.get("num_pages", 1)

    else:
        raise ValueError(f"Stratégie inconnue : {strategy}")

    chunked = []
    for i, chunk in enumerate(raw_chunks):
        chunked.append({
            "chunk_id": f"{document['filename']}_{strategy}_{i}",
            "text": chunk["text"],
            "title": chunk.get("title"),
            "subtitle": chunk.get("subtitle"),
            "page_number": chunk.get("page_number"),
            "total_pages": chunk.get("total_pages"),
            "source_file": document["filename"],
            "extractor_used": document["extractor_used"],
            "chunk_index": i,
            "chunk_method": strategy,
            "char_count": len(chunk["text"]),
            "is_table": chunk.get("is_table", False),
        })
    return chunked


# ============================================================
# FILTRAGE
# ============================================================

def is_informative_chunk(chunk_text, min_chars=100):
    cleaned = chunk_text.strip()
    if len(cleaned) < min_chars:
        return False
    alpha_chars = sum(1 for c in cleaned if c.isalpha())
    if alpha_chars < min_chars * 0.5:
        return False
    return True


def filter_chunks(chunks, min_chars=100, exempt_methods=("whole_page_detailed",),
                   filter_tables=True, max_whitespace_ratio=0.4, min_word_length_avg=3):
    kept, rejected = [], []
    for chunk in chunks:
        if chunk["chunk_method"] in exempt_methods:
            kept.append(chunk)
            continue

        if not is_informative_chunk(chunk["text"], min_chars):
            chunk["rejection_reason"] = "trop_court_ou_peu_alpha"
            rejected.append(chunk)
            continue

        is_table = chunk.get("is_table", False) or is_table_like_chunk(
            chunk["text"], max_whitespace_ratio, min_word_length_avg
        )
        if filter_tables and is_table:
            chunk["rejection_reason"] = "type_tableau"
            rejected.append(chunk)
            continue

        kept.append(chunk)

    return kept, rejected