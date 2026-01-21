import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.handlers.models import (
    PathPayload,
    BatteryPayload,
    ArrivePayload,
    RemovePathPayload,
)
from app.domain.path.service import bfs, format_path
from app.util.redis.init_data import release_node, release_robot_nodes


class CommandHandler(MQTTHandler):
    """로봇 명령 핸들러 - 토픽 마지막 부분으로 명령 구분"""

    @property
    def topic(self) -> str:
        return "+/+/robot/+"

    def handle(self, topic: str, payload: str) -> None:
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
        data = PathPayload(**json.loads(payload))
        # BFS로 경로 계산
        path, directions = bfs(data.current_node, data.final_node)

        if path:
            path_str = format_path(data.final_node, data.current_node, path, directions)
            # TODO: MQTT로 경로 발행
        else:
            return

    def _handle_battery(self, map_name: str, robot_id: str, payload: str) -> None:
        data = BatteryPayload(**json.loads(payload))
        # TODO: 배터리 상태 처리 로직

    def _handle_arrive(self, map_name: str, robot_id: str, payload: str) -> None:
        """로봇 도착 처리 - 해당 로봇이 점유한 모든 노드 해제"""
        data = ArrivePayload(**json.loads(payload))
        # 해당 로봇이 점유한 모든 노드 해제
        released_count = release_robot_nodes(robot_id)
        print(f"[Arrive] Robot {robot_id} arrived at node {data.node}. Released {released_count} nodes.")

    def _handle_remove(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 노드 해제 - 특정 노드의 점유 해제"""
        data = RemovePathPayload(**json.loads(payload))
        # 해당 노드가 이 로봇이 점유한 노드인지 확인 후 해제
        success = release_node(data.node, robot_id)
        if success:
            print(f"[Remove] Robot {robot_id} released node {data.node}.")
        else:
            print(f"[Remove] Failed to release node {data.node} for robot {robot_id}.")
