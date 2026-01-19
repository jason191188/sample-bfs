from abc import ABC, abstractmethod


class MQTTHandler(ABC):
    """MQTT 메시지 핸들러 베이스 클래스"""

    @property
    @abstractmethod
    def topic(self) -> str:
        """구독할 토픽"""
        pass

    @abstractmethod
    def handle(self, topic: str, payload: str) -> None:
        """메시지 처리"""
        pass
