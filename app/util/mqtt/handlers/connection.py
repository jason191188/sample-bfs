"""MQTT 클라이언트 연결/종료 이벤트 핸들러"""
import json
from datetime import datetime
from typing import Optional

from app.util.mqtt.handler import MQTTHandler
from app.util.redis.client import redis_service


class ConnectionHandler(MQTTHandler):
    """MQTT 브로커의 클라이언트 연결/종료 이벤트 핸들러

    클라이언트 ID 형식: {deviceName}-{mapName}-{deviceId}-{UUID}
    예시: robot-smartfarm_gangnam-1-a1b2c3d4-e5f6-7890-abcd-ef1234567890

    Redis 키 구조 (연결 시 생성, 해제 시 삭제):
        mqtt:connection:{deviceName}:{mapName}:{deviceId}
            - status: "connected"
            - connected_at: 연결 시간
            - ip: IP 주소
            - device_name: 디바이스 이름
            - device_id: 디바이스 ID
            - map_name: 맵 이름
            - uuid: UUID

    구독 토픽:
        - events/client/connected
        - events/client/disconnected
    """

    REDIS_KEY_PREFIX = "mqtt:connection:"

    @property
    def topic(self) -> str:
        return "events/client/#"

    def _parse_client_id(self, client_id: str) -> Optional[dict]:
        """clientid를 구성 요소로 파싱

        형식: {deviceName}-{mapName}-{deviceId}-{UUID}
        UUID 안에 하이픈이 포함되어 있으므로 앞 3개만 분리합니다.

        Args:
            client_id: MQTT 클라이언트 ID

        Returns:
            파싱된 정보 dict, 실패 시 None
        """
        parts = client_id.split("-", 3)
        if len(parts) != 4:
            return None

        device_name, map_name, device_id, uuid = parts
        if not device_name or not map_name or not device_id or not uuid:
            return None

        return {
            "device_name": device_name,
            "map_name": map_name,
            "device_id": device_id,
            "uuid": uuid,
        }

    def _get_connection_key(self, device_name: str, map_name: str, device_id: str) -> str:
        return f"{self.REDIS_KEY_PREFIX}{device_name}:{map_name}:{device_id}"

    def handle(self, topic: str, payload: str) -> None:
        if topic == "events/client/connected":
            self._handle_client_connected(payload)
        elif topic == "events/client/disconnected":
            self._handle_client_disconnected(payload)
        else:
            print(f"[Connection] Unknown event topic: {topic}")

    def _handle_client_connected(self, payload: str) -> None:
        """클라이언트 연결 시 파싱된 정보를 Redis에 저장"""
        try:
            client_info = json.loads(payload)
        except json.JSONDecodeError:
            print(f"[Connection] Connected - payload 파싱 실패: {payload}")
            return

        client_id = client_info.get("clientid", "")
        ip_address = client_info.get("ipaddress", "Unknown")

        parsed = self._parse_client_id(client_id)
        if not parsed:
            print(f"[Connection] Connected - clientid 형식 불가: {client_id}")
            return

        now = datetime.now().isoformat()
        key = self._get_connection_key(parsed["device_name"], parsed["map_name"], parsed["device_id"])

        # 연결 정보 저장
        redis_service.hset(key, "status", "connected")
        redis_service.hset(key, "connected_at", now)
        redis_service.hset(key, "ip", ip_address)
        redis_service.hset(key, "device_name", parsed["device_name"])
        redis_service.hset(key, "device_id", parsed["device_id"])
        redis_service.hset(key, "map_name", parsed["map_name"])
        redis_service.hset(key, "uuid", parsed["uuid"])
        # 이전 해제 정보 초기화
        redis_service.hdel(key, "disconnected_at")
        redis_service.hdel(key, "reason")

        print(f"[Connection] ✅ Connected - {parsed['device_name']}({parsed['map_name']}:{parsed['device_id']}), IP: {ip_address}")

    def _handle_client_disconnected(self, payload: str) -> None:
        """클라이언트 해제 시 Redis 키 삭제"""
        try:
            client_info = json.loads(payload)
        except json.JSONDecodeError:
            print(f"[Connection] Disconnected - payload 파싱 실패: {payload}")
            return

        client_id = client_info.get("clientid", "")
        reason = client_info.get("reason", "Unknown")

        parsed = self._parse_client_id(client_id)
        if not parsed:
            print(f"[Connection] Disconnected - clientid 형식 불가: {client_id}")
            return

        key = self._get_connection_key(parsed["device_name"], parsed["map_name"], parsed["device_id"])
        redis_service.delete(key)

        print(f"[Connection] ❌ Disconnected - {parsed['device_name']}({parsed['map_name']}:{parsed['device_id']}), Reason: {reason}")
