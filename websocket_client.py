import json
import queue
import time

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect


WS_URL = "ws://127.0.0.1:8000/ws"


def listen_for_records(messages: queue.Queue) -> None:
    """Reçoit les nouveaux records et les place dans une file."""

    while True:
        try:
            with connect(WS_URL, open_timeout=3) as websocket:
                while True:
                    message = json.loads(websocket.recv())

                    if (
                        isinstance(message, dict)
                        and message.get("type") == "new_record"
                    ):
                        messages.put(message)

        except (OSError, WebSocketException, json.JSONDecodeError):
            # Le serveur est indisponible : on réessaie après une pause.
            time.sleep(3)
