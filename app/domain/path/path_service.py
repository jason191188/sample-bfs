"""경로 계산 서비스 - BFS 기반 경로 탐색 및 MQTT 응답 전송"""
import json

from app.domain.path.service import bfs, cut_path, format_path
from app.util.mqtt.client import mqtt_service
from app.domain.robot.robot_state_service import robot_state_service


class PathCalculationService:
    """경로 계산 및 MQTT 응답 전송 서비스"""

    def calculate_and_send_path(
        self, map_name: str, robot_id: str, start_node: int, end_node: int, is_return: bool = False
    ) -> None:
        """경로 계산 및 MQTT 응답 전송

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            start_node: 시작 노드
            end_node: 목적지 노드
            is_return: 복귀 경로 여부
        """
        path_str, actual_end = self._calculate_path(map_name, start_node, end_node, robot_id)
        self._send_path_response(map_name, robot_id, start_node, end_node, path_str, actual_end, is_return)

    def _parse_path_nodes(self, path_str: str) -> list[int]:
        """경로 문자열에서 순서대로 방문할 노드 목록 추출

        Format: {final_node}/{final_dir}~{end}!{start},{dir}/{n1},{dir}/...
        반환: [start, n1, n2, ..., end] 순서의 노드 ID 리스트
        """
        try:
            left, right = path_str.split("!")
            end_node = int(left.split("~")[1])
            nodes = []
            for segment in right.rstrip("/").split("/"):
                if segment:
                    nodes.append(int(segment.split(",")[0]))
            nodes.append(end_node)
            return nodes
        except Exception:
            return []

    def _calculate_path(self, map_name: str, start_node: int, end_node: int, robot_id: str) -> tuple[str | None, int]:
        """BFS 경로 계산

        Args:
            map_name: 맵 이름
            start_node: 시작 노드
            end_node: 목적지 노드
            robot_id: 로봇 ID

        Returns:
            (경로 문자열, 실제 도착 노드) 또는 (None, end_node) if no path
        """
        path, directions = bfs(map_name, start_node, end_node)

        if not path:
            return None, end_node

        path, directions = cut_path(map_name, path, directions, robot_id)

        print(f"[Path] {path}")
        if len(path) <= 1:
            return None, end_node

        actual_end = path[-1]
        path_str = format_path(actual_end, start_node, path, directions, end_node)

        print(f"[Path] Formatted path: {path_str}")
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

            # 주행 검증용 노드 순서 저장
            path_nodes = self._parse_path_nodes(path_str)
            if path_nodes:
                redis_service.hset(path_key, "path_nodes", ",".join(str(n) for n in path_nodes))
                redis_service.hset(path_key, "path_index", "0")

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
