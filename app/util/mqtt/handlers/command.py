import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.handlers.models import (
    PathPayload,
    BatteryPayload,
    ArrivePayload,
    RemovePathPayload,
)
from app.util.redis.init_data import release_node, release_robot_nodes
from app.domain.path.path_service import path_calculation_service
from app.domain.robot.robot_state_service import robot_state_service


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

    def _determine_destination(self, current_node: int, final_node: int) -> tuple[int, bool]:
        """목적지 결정 (복귀 로직)

        Args:
            current_node: 현재 노드
            final_node: 요청된 목적지 (0이면 복귀 시그널)

        Returns:
            (실제 목적지, 복귀 여부)
        """
        if final_node == 0:
            # 복귀 시그널
            if current_node == 1:
                return 2, True  # 1번 노드에서 복귀 → 2번 노드
            else:
                return 1, True  # 그 외 노드에서 복귀 → 1번 노드
        else:
            # 일반 경로 요청
            return final_node, False

    def _handle_path(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 계산 요청 처리 - BFS로 경로 계산 후 MQTT로 응답"""
        data = PathPayload(**json.loads(payload))

        # 목적지 결정 (복귀 로직 처리)
        destination, is_return = self._determine_destination(data.current_node, data.final_node)

        if is_return:
            print(f"[Path] Robot {robot_id}: Return signal detected (node {data.current_node} → {destination})")
        else:
            print(f"[Path] Robot {robot_id}: Path request (node {data.current_node} → {destination})")

        # Redis에 로봇 위치 정보 저장
        robot_state_service.update_position(map_name, robot_id, data.current_node, destination)
        robot_state_service.update_status(map_name, robot_id, "moving")

        # PathCalculationService를 사용하여 경로 계산 및 응답
        path_calculation_service.calculate_and_send_path(map_name, robot_id, data.current_node, destination, is_return)

    def _handle_battery(self, map_name: str, robot_id: str, payload: str) -> None:
        """배터리 상태 처리 - Redis에 저장"""
        data = BatteryPayload(**json.loads(payload))

        # Redis에 배터리 정보 저장
        robot_state_service.update_battery(map_name, robot_id, data.level)
        print(f"[Battery] Robot {robot_id}: Battery level {data.level}% saved to Redis")

    def _handle_arrive(self, map_name: str, robot_id: str, payload: str) -> None:
        """로봇 도착 처리 - 해당 로봇이 점유한 모든 노드 해제"""
        data = ArrivePayload(**json.loads(payload))

        # Redis에 로봇 상태 저장 (도착)
        robot_state_service.update_status(map_name, robot_id, "arrived", data.node)

        # 해당 로봇이 점유한 모든 노드 해제
        released_count = release_robot_nodes(map_name, robot_id)
        print(f"[Arrive] Robot {robot_id} arrived at node {data.node}. Released {released_count} nodes.")

    def _handle_remove(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 노드 해제 - 특정 노드의 점유 해제"""
        data = RemovePathPayload(**json.loads(payload))
        # 해당 노드가 이 로봇이 점유한 노드인지 확인 후 해제
        success = release_node(map_name, data.node, robot_id)
        if success:
            print(f"[Remove] Robot {robot_id} released node {data.node}.")
        else:
            print(f"[Remove] Failed to release node {data.node} for robot {robot_id}.")
