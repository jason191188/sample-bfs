import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.handlers.models import PathPayload, BatteryPayload, ArrivePayload
from app.domain.path.service import bfs, format_path


class CommandHandler(MQTTHandler):
    """로봇 명령 핸들러 - 토픽 마지막 부분으로 명령 구분"""

    @property
    def topic(self) -> str:
        return "+/+/robot/+"

    def handle(self, topic: str, payload: str) -> None:
        print("test")
        parts = topic.split("/")
        if len(parts) != 4:
            return

        map_name, robot_id, _, command = parts

        if command == "path_plan":
            self._handle_path(map_name, robot_id, payload)
        elif command == "battery":
            self._handle_battery(map_name, robot_id, payload)
        elif command == "arrive":
            self._handle_arrive(map_name, robot_id, payload)
        elif command == "remove_path":
            self._handle_remove(map_name, robot_id, payload)

    def _handle_path(self, map_name: str, robot_id: str, payload: str) -> None:
        print(f"[CommandHandler] 경로 요청: map={map_name}, robot={robot_id}")
        data = PathPayload(**json.loads(payload))
        print("test")
        # BFS로 경로 계산
        path, directions = bfs(data.current_node, data.final_node)

        if path:
            path_str = format_path(data.final_node, data.current_node, path, directions)
            print(f"[CommandHandler] 경로 계산 완료: {path_str}")
            # TODO: MQTT로 경로 발행
        else:
            print(f"[CommandHandler] 경로 없음: {data.current_node} -> {data.final_node}")

    def _handle_battery(self, map_name: str, robot_id: str, payload: str) -> None:
        print(f"[CommandHandler] 배터리 상태: map={map_name}, robot={robot_id}")
        data = BatteryPayload(**json.loads(payload))
        print(f"[CommandHandler] 배터리 잔량: {data.level}%")
        # TODO: 배터리 상태 처리 로직

    def _handle_arrive(self, map_name: str, robot_id: str, payload: str) -> None:
        print(f"[CommandHandler] 도착 알림: map={map_name}, robot={robot_id}")
        data = ArrivePayload(**json.loads(payload))
        print(f"[CommandHandler] 도착 노드: {data.node}")
        # TODO: 도착 처리 로직

    def _handle_remove(self, map_name: str, robot_id: str, payload: str) -> None:
        print(f"[CommandHandler] 경로 삭제: map={map_name}, robot={robot_id}, payload={payload}")
        # TODO: 경로 삭제 로직
