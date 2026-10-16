import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

app = FastAPI(title="Dog Guesser API")

DATA_DIR = Path(__file__).parent / "data"
RECORD_FILE = DATA_DIR / "global_record.json"
LEADERBOARD_FILE = DATA_DIR / "leaderboard.json"

MAX_PLAYERS = 10


# --------------------------------------------------
# CONNEXIONS WEBSOCKET
# --------------------------------------------------

class ConnectionManager:
    """Gère les clients connectés au serveur WebSocket."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Envoie un message à tous les clients connectés."""

        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

class ScoreSubmission(BaseModel):
    """Données reçues à la fin d'une partie."""

    pseudo: str = Field(min_length=1, max_length=20)
    score: int = Field(ge=0, strict=True)

    @field_validator("pseudo")
    @classmethod
    def validate_pseudo(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Le pseudo ne peut pas être vide.")

        if len(value) > 20:
            raise ValueError("Le pseudo est trop long.")

        return value


# --------------------------------------------------
# OUTILS DE STOCKAGE JSON
# --------------------------------------------------

def read_json_file(path: Path, default):
    """Lit un fichier JSON ou retourne une valeur par défaut."""

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Impossible de lire {path.name}.",
        ) from error


def write_json_file(path: Path, data) -> None:
    """Écrit un fichier JSON en remplaçant le fichier après écriture."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )
            file.write("\n")

        temp_file.replace(path)

    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail=f"Impossible de sauvegarder {path.name}.",
        ) from error

    finally:
        temp_file.unlink(missing_ok=True)


# --------------------------------------------------
# RECORD GLOBAL
# --------------------------------------------------

def load_global_record() -> dict:
    """Charge le meilleur score de tous les joueurs."""

    data = read_json_file(
        RECORD_FILE,
        {"pseudo": None, "score": 0},
    )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail="Format du record global invalide.",
        )

    pseudo = data.get("pseudo")
    score = data.get("score")

    if (
        isinstance(score, bool)
        or not isinstance(score, int)
        or score < 0
    ):
        raise HTTPException(
            status_code=500,
            detail="Score global invalide.",
        )

    if pseudo is not None and not isinstance(pseudo, str):
        raise HTTPException(
            status_code=500,
            detail="Pseudo du record global invalide.",
        )

    return {
        "pseudo": pseudo,
        "score": score,
    }


def save_global_record(pseudo: str, score: int) -> None:
    write_json_file(
        RECORD_FILE,
        {"pseudo": pseudo, "score": score},
    )


# --------------------------------------------------
# CLASSEMENT
# --------------------------------------------------

def load_leaderboard() -> list:
    """Charge et valide le classement."""

    data = read_json_file(LEADERBOARD_FILE, [])

    if not isinstance(data, list):
        raise HTTPException(
            status_code=500,
            detail="Format du classement invalide.",
        )

    for player in data:
        if not isinstance(player, dict):
            raise HTTPException(
                status_code=500,
                detail="Entrée de classement invalide.",
            )

        pseudo = player.get("pseudo")
        score = player.get("score")

        if (
            not isinstance(pseudo, str)
            or not pseudo.strip()
            or len(pseudo) > 20
            or isinstance(score, bool)
            or not isinstance(score, int)
            or score < 0
        ):
            raise HTTPException(
                status_code=500,
                detail="Données de classement invalides.",
            )

    return data


def save_leaderboard(players: list) -> None:
    write_json_file(LEADERBOARD_FILE, players)


def sort_leaderboard(players: list) -> list:
    """Trie les scores du plus élevé au plus faible."""

    return sorted(
        players,
        key=lambda player: player["score"],
        reverse=True,
    )[:MAX_PLAYERS]


# --------------------------------------------------
# ROUTES HTTP
# --------------------------------------------------

@app.get("/")
def home() -> dict:
    return {"message": "Dog Guesser API opérationnelle !"}


@app.get("/record")
def get_record() -> dict:
    return load_global_record()


@app.post("/record")
async def submit_score(submission: ScoreSubmission) -> dict:
    """Met à jour le record global et le classement."""

    pseudo = submission.pseudo
    score = submission.score

    # Met à jour le classement du joueur.
    players = load_leaderboard()

    existing_player = next(
        (
            player
            for player in players
            if player["pseudo"].casefold() == pseudo.casefold()
        ),
        None,
    )

    if existing_player is not None:
        if score > existing_player["score"]:
            existing_player["score"] = score
    else:
        players.append({
            "pseudo": pseudo,
            "score": score,
        })

    players = sort_leaderboard(players)
    save_leaderboard(players)

    # Met à jour le record global si nécessaire.
    current_record = load_global_record()
    record_beaten = score > current_record["score"]

    if record_beaten:
        save_global_record(pseudo, score)
        current_record = {
            "pseudo": pseudo,
            "score": score,
        }
        await manager.broadcast({
            "type": "new_record",
            "pseudo": pseudo,
            "score": score,
         })


    return {
        "record_beaten": record_beaten,
        "pseudo": current_record["pseudo"],
        "score": current_record["score"],
        "personal_best": next(
            (
                player["score"]
                for player in players
                if player["pseudo"].casefold() == pseudo.casefold()
            ),
            score,
        ),
    }


@app.get("/leaderboard")
def get_leaderboard() -> dict:
    """Retourne les dix meilleurs joueurs."""

    players = sort_leaderboard(load_leaderboard())

    return {
        "leaderboard": players,
        "total_players": len(players),
    }


# --------------------------------------------------
# WEBSOCKET
# --------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Maintient la connexion ouverte jusqu'à la déconnexion."""

    await manager.connect(websocket)

    try:
        while True:
            # Attend un message pour détecter la fermeture du client.
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
