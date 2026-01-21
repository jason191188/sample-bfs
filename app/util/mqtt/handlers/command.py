import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.handlers.models import (
    PathPayload,
    BatteryPayload,
    ArrivePayload,
    RemovePathPayload,
)
from app.domain.path.service import bfs, cut_path, format_path
from app.util.redis.init_data import release_node, release_robot_nodes
from app.util.mqtt.client import mqtt_service


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

        # BFS로 경로 계산 및 응답
        self._calculate_and_send_path(map_name, robot_id, data.current_node, destination, is_return)

    def _calculate_forward_path(self, start_node: int, end_node: int, robot_id: str) -> tuple[str | None, int]:
        """전진 경로 계산

        Args:
            start_node: 시작 노드
            end_node: 목적지 노드
            robot_id: 로봇 ID

        Returns:
            (경로 문자열, 실제 도착 노드) 또는 (None, end_node) if no path
        """
        # 1. BFS로 전체 최단 경로 계산
        path, directions = bfs(start_node, end_node)

        if not path:
            return None, end_node

        # 2. 점유된 노드를 고려하여 경로 자르기
        path, directions = cut_path(path, directions, robot_id)

        # 3. 경로가 시작 노드만 남은 경우 (이동 불가)
        if len(path) <= 1:
            return None, end_node

        # 4. 경로 문자열 생성
        actual_end = path[-1]
        path_str = format_path(actual_end, start_node, path, directions)

        return path_str, actual_end

    def _calculate_return_path(self, start_node: int, end_node: int, robot_id: str) -> tuple[str | None, int]:
        """복귀 경로 계산 (현재는 전진 경로와 동일한 로직)

        Args:
            start_node: 시작 노드
            end_node: 복귀 목적지 노드 (1 또는 2)
            robot_id: 로봇 ID

        Returns:
            (경로 문자열, 실제 도착 노드) 또는 (None, end_node) if no path
        """
        # 복귀 경로도 동일한 BFS + cut_path 로직 사용
        return self._calculate_forward_path(start_node, end_node, robot_id)

    def _send_path_response(self, map_name: str, robot_id: str, start_node: int, end_node: int,
                           path_str: str | None, actual_end: int, is_return: bool = False) -> None:
        """MQTT 경로 응답 전송

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            start_node: 시작 노드
            end_node: 요청된 목적지 노드
            path_str: 경로 문자열 (None이면 경로 없음/차단)
            actual_end: 실제 도착 노드
            is_return: 복귀 경로 여부
        """
        response_topic = f"{map_name}/{robot_id}/server/path_plan"

        if path_str is None:
            # 경로를 찾지 못했거나 차단된 경우
            no_path_str = f"{end_node}!/d~{start_node}"
            response_payload = json.dumps({"path": no_path_str})
            mqtt_service.publish(response_topic, response_payload)

            if is_return:
                print(f"[Path] Robot {robot_id}: Return path blocked or not found ({start_node} → {end_node})")
            else:
                print(f"[Path] Robot {robot_id}: Path blocked or not found ({start_node} → {end_node})")
            return

        # 정상 경로 응답
        response_payload = json.dumps({"path": path_str})

        if mqtt_service.publish(response_topic, response_payload):
            path_type = "Return path" if is_return else "Path"
            print(f"[Path] Robot {robot_id}: {path_type} sent ({start_node} → {actual_end})")
            if actual_end != end_node:
                print(f"       Path cut at node {actual_end} (original destination: {end_node})")
        else:
            print(f"[Path] Robot {robot_id}: Failed to send path (MQTT not connected)")

    def _calculate_and_send_path(self, map_name: str, robot_id: str, start_node: int, end_node: int, is_return: bool = False) -> None:
        """경로 계산 및 MQTT 응답 전송 (통합 함수)"""
        if is_return:
            path_str, actual_end = self._calculate_return_path(start_node, end_node, robot_id)
        else:
            path_str, actual_end = self._calculate_forward_path(start_node, end_node, robot_id)

        self._send_path_response(map_name, robot_id, start_node, end_node, path_str, actual_end, is_return)

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
