import json
from datetime import datetime

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.client import mqtt_service


class StatusHandler(MQTTHandler):
    """MQTT 브로커 이벤트 핸들러 - 클라이언트 연결 이벤트 수신"""

    @property
    def topic(self) -> str:
        return "events/client/+"

    def handle(self, topic: str, payload: str) -> None:
        parts = topic.split("/")
        if len(parts) != 3:
            return

        _, _, event = parts
        data = json.loads(payload)
        client_id = data.get("clientid", "unknown")

        if event == "connected":
            time = datetime.fromtimestamp(data["connected_at"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[MQTT Event] Client connected: {client_id} at {time}")
        elif event == "disconnected":
            time = datetime.fromtimestamp(data["disconnected_at"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[MQTT Event] Client disconnected: {client_id} at {time} (reason: {data.get('reason', 'unknown')})")
            mqtt_service.publish("events/client/test", payload)
