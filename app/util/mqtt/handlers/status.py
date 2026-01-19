from app.util.mqtt.handler import MQTTHandler


class StatusHandler(MQTTHandler):
    """로봇 상태 핸들러"""

    @property
    def topic(self) -> str:
        return "robot/status"

    def handle(self, topic: str, payload: str) -> None:
        # TODO: 상태 처리 로직 구현
        # 예: 위치 업데이트, 배터리 상태 등
