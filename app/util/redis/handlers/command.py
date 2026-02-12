import json

from app.domain.robot.robot_state_service import robot_state_service
from app.domain.path.service import bfs
from app.util.redis.init_data import get_node
from app.util.redis.client import redis_service
from app.util.mqtt.client import mqtt_service


class RedisCommandHandler:
    """Redis Pub/Sub 명령 핸들러 - server/button 토픽으로 final_node 전송"""

    def handle_message(self, message: str) -> None:
        """Redis 채널 메시지 처리

        Args:
            message: JSON 형식의 메시지 (type, mapName, robotId 포함)
        """
        try:
            data = json.loads(message)
            command_type = data.get("type")
            map_name = data.get("farmName")
            robot_id = data.get("robotId")
            print(data)

            if not all([command_type, map_name, robot_id]):
                print(f"[Redis] Missing required fields: type, mapName, or robotId")
                return

            if command_type == "START":
                self._handle_start_command(map_name, robot_id)
            elif command_type == "NEXT":
                self._handle_next_command(map_name, robot_id)
            elif command_type == "RETURN":
                self._handle_return_command(map_name, robot_id)
            else:
                print(f"[Redis] Unknown command type: {command_type}")

        except json.JSONDecodeError as e:
            print(f"[Redis] Invalid JSON message: {e}")
        except Exception as e:
            print(f"[Redis] Error handling message: {e}")

    def _handle_start_command(self, map_name: str, robot_id: str) -> None:
        """Start 명령 처리 - 현재 노드의 왼쪽(l) 방향으로 이동"""
        # Redis에서 로봇 상태 조회
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found or missing current_node")
            return

        current_node = robot_state["current_node"]

        # 현재 노드 정보에서 왼쪽(l) 방향의 다음 노드 조회
        node_data = get_node(map_name, current_node)
        if not node_data:
            print(f"[Redis] Node {current_node} not found in map {map_name}")
            return

        next_node = node_data.get("l")
        if next_node is None or next_node == 0:
            print(f"[Redis] Robot {robot_id}: No left node available from node {current_node}")
            return

        print(f"[Redis/Button] Robot {robot_id}: Sending final_node (current: node {current_node} → next: node {next_node})")

        # MQTT server/button 토픽으로 final_node 전송
        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": next_node})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: final_node {next_node} sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send final_node (MQTT not connected)")

    def _calculate_next_position(self, map_name: str, current_node: str) -> str | None:
        """다음 위치 계산 - l 방향 전진

        Args:
            map_name: 맵 이름
            current_node: 현재 노드 ("5-2" 형태 또는 "5")

        Returns:
            다음 위치 ("5-3" 형태) 또는 None (이동 불가)

        로직:
            - sub == 0: l 방향 확인 후 회전 ({node}-1)
            - sub < 4: 순차 진행 ({node}-{sub+1})
            - sub == 4: l 방향의 다음 노드 ({next_node}-0)
        """
        current_node_str = str(current_node)

        # 현재 노드 파싱 ("2-4" → node_id=2, sub=4 / "2" → node_id=2, sub=0)
        if "-" in current_node_str:
            parts = current_node_str.split("-")
            node_id = int(parts[0])
            sub = int(parts[1])
        else:
            node_id = int(current_node_str)
            sub = 0

        # 다음 위치 계산
        if sub == 0:
            # sub == 0: l 방향에 다음 노드가 있는지 확인 후 회전하여 {node}-1로 이동
            node_data = get_node(map_name, node_id)

            if not node_data:
                print(f"[Redis/Next] Node {node_id} not found")
                return None

            # l 방향의 다음 노드 확인
            left_node_id = node_data.get("l", 0)

            if left_node_id == 0:
                # l 방향에 노드가 없으면 이동 불가
                print(f"[Redis/Next] At {node_id}-0, no left node available")
                return None

            # l 방향 노드가 있으면 회전하여 같은 노드의 1번으로 이동
            next_position = f"{node_id}-1"
            print(f"[Redis/Next] At {node_id}-0, rotating (left node {left_node_id} exists) → {next_position}")

        elif sub < 4:
            # 같은 노드 내 다음 서브포지션
            next_position = f"{node_id}-{sub + 1}"

        else:  # sub == 4
            # sub == 4: l 방향의 다음 노드 0번으로 이동
            node_data = get_node(map_name, node_id)

            if not node_data:
                print(f"[Redis/Next] Node {node_id} not found")
                return None

            # l 방향의 다음 노드 확인
            left_node_id = node_data.get("l", 0)

            if left_node_id == 0:
                # l 방향에 노드가 없으면 이동 불가
                print(f"[Redis/Next] At {node_id}-4, no left node available")
                return None

            # l 방향의 다음 노드 0번으로 이동
            next_position = f"{left_node_id}-0"
            print(f"[Redis/Next] At {node_id}-4, moving to next node → {next_position}")

        return next_position

    def _handle_next_command(self, map_name: str, robot_id: str) -> None:
        """Next 명령 처리 - 전진 요청 (l 방향)

        NEXT는 항상 전진 요청이며, 복귀는 RETURN 명령으로 별도 처리됩니다.
        진행 방향은 l 방향으로 고정되며, final_node의 영향을 받지 않습니다.
        """
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found")
            return

        current_node = robot_state["current_node"]

        # 다음 위치 계산
        next_position = self._calculate_next_position(map_name, current_node)

        if next_position is None:
            print(f"[Redis/Next] Robot {robot_id}: Cannot proceed from {current_node}")
            return

        print(f"[Redis/Next] Robot {robot_id}: {current_node} → {next_position}")

        # MQTT server/button 토픽으로 전송
        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": next_position})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: final_node {next_position} sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send (MQTT not connected)")



    def _handle_return_command(self, map_name: str, robot_id: str) -> None:
        """Return 명령 처리 - 로봇 상태를 RETURN으로 변경하고 복귀 노드 전송"""
        # Redis에서 로봇 상태 조회
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found or missing current_node")
            return

        current_node = robot_state["current_node"]

        # 복귀 목적지 (충전소: 1-0)
        final_node = "1-0"

        # 로봇 상태를 RETURN으로 변경 (final_node를 1-0으로 설정하면 자동으로 RETURN 상태가 됨)
        robot_state_service.update_position(map_name, robot_id, current_node, final_node)

        print(f"[Redis/Return] Robot {robot_id}: Return command executed (current: {current_node}, final_node: {final_node}, status: RETURN)")

        # MQTT server/button 토픽으로 final_node 전송
        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": final_node})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: Return signal (final_node: {final_node}) sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send return signal (MQTT not connected)")


redis_command_handler = RedisCommandHandler()
