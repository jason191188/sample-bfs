"""경로 계산 서비스 - BFS 기반 경로 탐색 및 MQTT 응답 전송"""
import json

from app.domain.path.service import bfs, cut_path, format_path
from app.util.mqtt.client import mqtt_service
from app.domain.robot.robot_state_service import robot_state_service


class PathCalculationService:
    """경로 계산 및 MQTT 응답 전송 서비스"""

    def calculate_and_send_path(
        self, map_name: str, robot_id: str, start_node: int, end_node: int, is_return: bool = False, start_display: str = None, final_display: str = None
    ) -> None:
        """경로 계산 및 MQTT 응답 전송

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            start_node: 시작 노드
            end_node: 목적지 노드
            is_return: 복귀 경로 여부
            start_display: 시작 노드 표시 문자열 ("2-1" 등)
            final_display: 목적지 표시 문자열 ("4-1" 등)
        """
        if is_return:
            path_str, actual_end = self._calculate_return_path(map_name, start_node, end_node, robot_id, start_display, final_display)
        else:
            path_str, actual_end = self._calculate_forward_path(map_name, start_node, end_node, robot_id, start_display, final_display)

        self._send_path_response(map_name, robot_id, start_node, end_node, path_str, actual_end, is_return)

    def _calculate_forward_path(self, map_name: str, start_node: int, end_node: int, robot_id: str, start_display: str = None, final_display: str = None) -> tuple[str | None, int]:
        """전진 경로 계산

        Args:
            map_name: 맵 이름
            start_node: 시작 노드
            end_node: 목적지 노드
            robot_id: 로봇 ID
            start_display: 시작 노드 표시 문자열 ("2-1" 등)
            final_display: 목적지 표시 문자열 ("4-1" 등)

        Returns:
            (경로 문자열, 실제 도착 노드) 또는 (None, end_node) if no path
        """
        # 1. BFS로 전체 최단 경로 계산
        path, directions = bfs(map_name, start_node, end_node)

        if not path:
            return None, end_node

        # 2. 점유된 노드를 고려하여 경로 자르기
        path, directions = cut_path(map_name, path, directions, robot_id)

        # 3. 경로가 시작 노드만 남은 경우 (이동 불가)
        if len(path) <= 1:
            return None, end_node

        # 4. 경로 문자열 생성
        actual_end = path[-1]
        path_str = format_path(actual_end, start_node, path, directions, end_node, start_display, final_display)

        return path_str, actual_end

    def _calculate_return_path(self, map_name: str, start_node: int, end_node: int, robot_id: str, start_display: str = None, final_display: str = None) -> tuple[str | None, int]:
        """복귀 경로 계산 - 서브노드 위치에 따라 다르게 처리

        Args:
            map_name: 맵 이름
            start_node: 시작 노드
            end_node: 복귀 목적지 노드 (1)
            robot_id: 로봇 ID
            start_display: 시작 노드 표시 문자열 ("5-3" 등)
            final_display: 목적지 표시 문자열 ("1-0" 등)

        Returns:
            (경로 문자열, 실제 도착 노드) 또는 (None, end_node) if no path
        """
        # start_display에서 서브노드 위치 확인
        current_sub = 0
        if start_display and "-" in start_display:
            parts = start_display.split("-")
            if len(parts) == 2:
                current_sub = int(parts[1])

        # 서브노드가 0이 아닌 경우: 먼저 현재 노드의 0번 위치로 이동 후 복귀
        if current_sub != 0:
            # 예: "56-3" → "56-2" → "56-1" → "56-0" → "55-0" → ... → "1-0"
            print(f"[Return] Robot {robot_id}: Starting return from sub-position {current_sub}, moving to 0 first")

            # BFS로 전체 경로 계산 (start_node → end_node)
            path, directions = bfs(map_name, start_node, end_node)

            if not path:
                return None, end_node

            # 점유된 노드를 고려하여 경로 자르기
            path, directions = cut_path(map_name, path, directions, robot_id)

            if len(path) <= 1:
                return None, end_node

            actual_end = path[-1]

            # 복귀 방향은 BFS 첫 번째 방향 (보통 'r')
            return_direction = directions[0] if directions else "r"

            # 서브노드 리스트 생성: [(node_id, sub, direction), ...]
            sub_nodes = []

            # 1) 현재 노드에서 서브포지션을 감소시키며 0까지 이동 (r 방향)
            for sub in range(current_sub - 1, -1, -1):  # current_sub-1 → 0까지 감소
                sub_nodes.append((start_node, sub, return_direction))

            # 2) 다음 노드들은 모두 -0 형태만 (서브노드 1,2,3,4 건너뛰기)
            for i in range(1, len(path)):
                sub_nodes.append((path[i], 0, return_direction))

            if len(sub_nodes) == 0:
                return None, end_node

            # MQTT 경로 문자열 생성 (MQTT handler의 _handle_sub_node_path와 동일한 형식)
            start_display = f"{sub_nodes[0][0]}-{sub_nodes[0][1]}"
            end_display = f"{sub_nodes[-1][0]}-{sub_nodes[-1][1]}"
            final_display = f"{end_node}-0"

            path_str = f"{final_display}/{return_direction}~{end_display}!{start_display},{return_direction}/"
            for i in range(1, len(sub_nodes) - 1):
                nid, s, d = sub_nodes[i]
                path_str += f"{nid}-{s},{d}/"

            return path_str, actual_end

        # 서브노드가 0인 경우: 바로 복귀 경로 계산
        else:
            # 예: "56-0" → "55-0" → "54-0" → ... → "1-0"
            print(f"[Return] Robot {robot_id}: Starting return from position 0, direct return")

            # BFS로 전체 경로 계산
            path, directions = bfs(map_name, start_node, end_node)

            if not path:
                return None, end_node

            # 점유된 노드를 고려하여 경로 자르기
            path, directions = cut_path(map_name, path, directions, robot_id)

            if len(path) <= 1:
                return None, end_node

            actual_end = path[-1]

            # 복귀 방향은 BFS 첫 번째 방향 (보통 'r')
            return_direction = directions[0] if directions else "r"

            # 서브노드 리스트 생성: 모든 노드를 -0 형태로 (서브노드 1,2,3,4 건너뛰기)
            sub_nodes = []
            for node_id in path:
                sub_nodes.append((node_id, 0, return_direction))

            if len(sub_nodes) == 0:
                return None, end_node

            # MQTT 경로 문자열 생성
            start_display = f"{sub_nodes[0][0]}-{sub_nodes[0][1]}"
            end_display = f"{sub_nodes[-1][0]}-{sub_nodes[-1][1]}"
            final_display = f"{end_node}-0"

            path_str = f"{final_display}/{return_direction}~{end_display}!{start_display},{return_direction}/"
            for i in range(1, len(sub_nodes) - 1):
                nid, s, d = sub_nodes[i]
                path_str += f"{nid}-{s},{d}/"

            return path_str, actual_end

    def _send_path_response(
        self,
        map_name: str,
        robot_id: str,
        start_node: int,
        end_node: int,
        path_str: str | None,
        actual_end: int,
        is_return: bool = False,
    ) -> None:
        """MQTT 경로 응답 전송 및 Redis 저장"""
        from app.util.redis.client import redis_service

        response_topic = f"{map_name}/{robot_id}/server/path_plan"

        if path_str is None:
            # 경로를 찾지 못했거나 차단된 경우
            no_path_str = f"{end_node}!/d~{start_node}"
            response_payload = json.dumps({"path": no_path_str})
            mqtt_service.publish(response_topic, response_payload)

            # Redis에 경로 저장 (실패 경로도 저장)
            path_key = f"robot:path:{map_name}:{robot_id}"
            redis_service.hset(path_key, "path", no_path_str)
            redis_service.hset(path_key, "status", "blocked")
            redis_service.hset(path_key, "start_node", str(start_node))
            redis_service.hset(path_key, "end_node", str(end_node))

            if is_return:
                print(f"[Path] Robot {robot_id}: Return path blocked or not found ({start_node} → {end_node})")
            else:
                print(f"[Path] Robot {robot_id}: Path blocked or not found ({start_node} → {end_node})")
            return

        # 정상 경로 응답
        response_payload = json.dumps({"path": path_str})

        if mqtt_service.publish(response_topic, response_payload):
            # Redis에 경로 저장
            path_key = f"robot:path:{map_name}:{robot_id}"
            redis_service.hset(path_key, "path", path_str)
            redis_service.hset(path_key, "status", "success")
            redis_service.hset(path_key, "start_node", str(start_node))
            redis_service.hset(path_key, "end_node", str(end_node))
            redis_service.hset(path_key, "actual_end", str(actual_end))
            redis_service.hset(path_key, "is_return", str(is_return))

            print(f"[Path] Robot {robot_id}: Path saved to Redis (key: {path_key})")

            # 상태 변경 로직
            status_msg = ""
            if is_return:
                # 복귀 경로인 경우 "return"으로 변경
                robot_state_service.update_status(map_name, robot_id, "return")
                status_msg = " - Status: return"
            elif start_node == 2:
                # 2번 노드에서 출발하는 경우 "moving"으로 변경
                robot_state_service.update_status(map_name, robot_id, "moving")
                status_msg = " - Status: moving"

            path_type = "Return path" if is_return else "Path"
            print(f"[Path] Robot {robot_id}: {path_type} sent ({start_node} → {actual_end}){status_msg}")
            if actual_end != end_node:
                print(f"       Path cut at node {actual_end} (original destination: {end_node})")
        else:
            print(f"[Path] Robot {robot_id}: Failed to send path (MQTT not connected)")


# 싱글톤 인스턴스
path_calculation_service = PathCalculationService()
