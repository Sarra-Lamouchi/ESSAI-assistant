import os
import itertools


class GroqKeyRotator:
    """
    Gère la rotation entre plusieurs clés API Groq,
    pour répartir la charge de requêtes et éviter les limites de rate-limit
    d'un compte gratuit unique.

    Fonctionnement :
    - round-robin : chaque appel utilise la clé suivante dans l'ordre
    - failover : si une clé échoue (ex: rate limit atteint), on passe
      automatiquement à la suivante et on retente, jusqu'à épuisement
      de toutes les clés disponibles
    """

    def __init__(self, keys=None):
        """
        keys : liste explicite de clés, ou None pour les charger depuis
        les variables d'environnement GROQ_API_KEY_1 et _2
        """
        if keys is None:
            keys = [
                os.environ.get("GROQ_API_KEY_1"),
                os.environ.get("GROQ_API_KEY_2"),
            ]
        self.keys = [k for k in keys if k]  # retire les clés manquantes/None

        if not self.keys:
            raise ValueError(
                "Aucune clé Groq trouvée. Vérifie ton fichier .env "
                "(GROQ_API_KEY_1, _2)"
            )

        self._cycle = itertools.cycle(self.keys)
        print(f"✅ {len(self.keys)} clé(s) Groq chargée(s)")

    def get_next_key(self):
        """Retourne la prochaine clé dans la rotation (round-robin)"""
        return next(self._cycle)

    def get_all_keys_from(self, start_key):
        """
        Retourne la liste de toutes les clés, réordonnée pour commencer
        par start_key — utilisé pour le failover : si start_key échoue,
        on essaie les suivantes dans l'ordre, sans jamais répéter une clé
        déjà tentée pour cet appel.
        """
        idx = self.keys.index(start_key)
        return self.keys[idx:] + self.keys[:idx]