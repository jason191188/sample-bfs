import re
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

from app.config.settings import settings

if TYPE_CHECKING:
    from app.util.mqtt.handler import MQTTHandler


def mqtt_match(pattern: str, topic: str) -> bool:
    """MQTT 토픽 패턴 매칭 (+, # 와일드카드 지원)"""
    # + -> 단일 레벨 매칭, # -> 다중 레벨 매칭
    regex = pattern.replace("+", "[^/]+").replace("#", ".+")
    regex = f"^{regex}$"
    return re.match(regex, topic) is not None


class MQTTService:
    def __init__(self):
        self.broker = settings.mqtt.broker
        self.port = settings.mqtt.port
        self.client: mqtt.Client = None
        self._handlers: dict[str, "MQTTHandler"] = {}  # topic -> handler

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("MQTT 브로커 연결 성공")
            # 등록된 핸들러 토픽들 구독
            for topic in self._handlers.keys():
                client.subscribe(topic)
                print(f"MQTT 토픽 구독: {topic}")
            # 테스트 메시지 발행
            client.publish(settings.mqtt.pub_topic, "server connected")
            print(f"MQTT 테스트 메시지 발행: {settings.mqtt.pub_topic}")
        else:
            print(f"MQTT 연결 실패: {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        print(f"MQTT 수신 [{topic}]: {payload}")

        # 매칭되는 핸들러 호출
        for pattern, handler in self._handlers.items():
            if mqtt_match(pattern, topic):
                try:
                    handler.handle(topic, payload)
                except Exception as e:
                    print(f"핸들러 오류 [{pattern}]: {e}")

    def register_handler(self, handler: "MQTTHandler"):
        """핸들러 등록"""
        self._handlers[handler.topic] = handler
        print(f"MQTT 핸들러 등록: {handler.topic}")

        # 이미 연결된 상태면 바로 구독
        if self.client and self.client.is_connected():
            self.client.subscribe(handler.topic)
            print(f"MQTT 토픽 구독: {handler.topic}")

    def connect(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
        except Exception as e:
            print(f"MQTT 브로커 연결 실패: {e}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def subscribe(self, topic: str):
        """추가 토픽 구독"""
        if self.client and self.client.is_connected():
            self.client.subscribe(topic)
            print(f"MQTT 토픽 구독: {topic}")

    def publish(self, topic: str, payload: str) -> bool:
        if self.client and self.client.is_connected():
            self.client.publish(topic, payload)
            return True
        return False

    def is_connected(self) -> bool:
        return self.client and self.client.is_connected()


mqtt_service = MQTTService()
