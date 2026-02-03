"""MQTT 클라이언트 연결/종료 이벤트 핸들러"""
import json

from app.util.mqtt.handler import MQTTHandler


class ConnectionHandler(MQTTHandler):
    """MQTT 브로커의 클라이언트 연결/종료 이벤트 핸들러

    구독 토픽:
        - events/client/connected: 클라이언트가 브로커에 연결될 때
        - events/client/disconnected: 클라이언트가 브로커에서 연결이 끊어질 때

    Note:
        이 기능을 사용하려면 MQTT 브로커(예: Mosquitto)에서
        sys_interval 설정이 활성화되어 있어야 합니다.

        Mosquitto 설정 예시:
            sys_interval 10
            connection_messages true
    """

    @property
    def topic(self) -> str:
        # events/# 패턴으로 모든 이벤트 토픽 구독
        return "events/client/#"

    def handle(self, topic: str, payload: str) -> None:
        """MQTT 연결 이벤트 처리

        Args:
            topic: MQTT 토픽 (events/client/connected 또는 events/client/disconnected)
            payload: 이벤트 페이로드 (JSON 형식의 클라이언트 정보)
        """
        if topic == "events/client/connected":
            self._handle_client_connected(payload)
        elif topic == "events/client/disconnected":
            self._handle_client_disconnected(payload)
        else:
            print(f"[Connection] Unknown event topic: {topic}")

    def _handle_client_connected(self, payload: str) -> None:
        """클라이언트 연결 이벤트 처리

        Args:
            payload: 연결된 클라이언트 정보 (JSON)

        페이로드 예시:
            {
                "clientid": "robot_01",
                "username": "user",
                "ipaddress": "192.168.1.100",
                "clean_session": true,
                "protocol": 4
            }
        """
        try:
            # 페이로드 파싱 시도
            try:
                client_info = json.loads(payload)
                client_id = client_info.get("clientid", "Unknown")
                ip_address = client_info.get("ipaddress", "Unknown")
                print(f"[Connection] ✅ Client connected - ID: {client_id}, IP: {ip_address}")
            except json.JSONDecodeError:
                # JSON이 아닌 경우 원본 문자열 출력
                print(f"[Connection] ✅ Client connected - Raw: {payload}")

            # 필요한 경우 추가 로직 구현
            # 예: Redis에 연결 정보 저장, 알림 전송 등
            # redis_service.hset(f"mqtt:clients:{client_id}", "status", "connected")

        except Exception as e:
            print(f"[Connection] ❌ Error handling client_connected: {e}")

    def _handle_client_disconnected(self, payload: str) -> None:
        """클라이언트 연결 종료 이벤트 처리

        Args:
            payload: 연결 해제된 클라이언트 정보 (JSON)

        페이로드 예시:
            {
                "clientid": "robot_01",
                "username": "user",
                "reason": "normal"
            }
        """
        try:
            # 페이로드 파싱 시도
            try:
                client_info = json.loads(payload)
                client_id = client_info.get("clientid", "Unknown")
                reason = client_info.get("reason", "Unknown")
                print(f"[Connection] ❌ Client disconnected - ID: {client_id}, Reason: {reason}")
            except json.JSONDecodeError:
                # JSON이 아닌 경우 원본 문자열 출력
                print(f"[Connection] ❌ Client disconnected - Raw: {payload}")

            # 필요한 경우 추가 로직 구현
            # 예: Redis에서 연결 정보 삭제, 알림 전송, 재연결 시도 등
            # redis_service.hdel(f"mqtt:clients:{client_id}", "status")
            # redis_service.publish("mqtt:events", json.dumps({"event": "disconnect", "client": client_id}))

        except Exception as e:
            print(f"[Connection] ❌ Error handling client_disconnected: {e}")
