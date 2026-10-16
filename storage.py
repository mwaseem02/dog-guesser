import json
from pathlib import Path


# Dossier contenant les données persistantes du jeu.
DATA_DIR = Path(__file__).parent / "data"
RECORD_FILE = DATA_DIR / "personal_record.json"


def load_personal_record() -> int:
    """Retourne le record personnel sauvegardé, ou 0 s'il est absent."""

    # Si le fichier n'existe pas, aucun record n'a encore été sauvegardé.
    if not RECORD_FILE.exists():
        return 0

    try:
        with RECORD_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        # Vérifie la structure du JSON.
        if not isinstance(data, dict):
            return 0

        record = data.get("record", 0)

        # bool est une sous-classe de int en Python :
        # on l'exclut donc explicitement.
        if isinstance(record, bool):
            return 0

        # On accepte uniquement les entiers.
        if not isinstance(record, int) or record < 0:
            return 0

        return record

    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        # Fichier illisible ou contenu invalide.
        return 0


def save_personal_record(score: int) -> None:
    """Sauvegarde un record personnel valide."""

    # Refuse les scores qui ne sont pas des entiers positifs ou nuls.
    if isinstance(score, bool) or not isinstance(score, int) or score < 0:
        raise ValueError("Le score doit être un entier positif ou nul.")

    # Crée le dossier si nécessaire.
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Écrit dans un fichier temporaire pour limiter le risque
    # de corrompre le record existant si l'écriture échoue.
    temp_file = RECORD_FILE.with_suffix(".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump({"record": score}, file, indent=4)
            file.write("\n")

        # Remplace le fichier précédent après une écriture réussie.
        temp_file.replace(RECORD_FILE)

    finally:
        # Nettoie le fichier temporaire s'il existe encore.
        temp_file.unlink(missing_ok=True)
