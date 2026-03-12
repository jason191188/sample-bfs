import json

from app.domain.robot.robot_state_service import robot_state_service
from app.domain.robot.robot_status import RobotStatus
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
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found or missing current_node")
            return

        current_node = robot_state["current_node"]

        node_data = get_node(map_name, current_node)
        if not node_data:
            print(f"[Redis] Node {current_node} not found in map {map_name}")
            return

        next_node = node_data.get("l")
        if not next_node or next_node == 0:
            print(f"[Redis] Robot {robot_id}: No left node available from node {current_node}")
            return

        print(f"[Redis/Button] Robot {robot_id}: Sending final_node (current: node {current_node} → next: node {next_node})")

        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": next_node})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: final_node {next_node} sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send final_node (MQTT not connected)")

    def _handle_next_command(self, map_name: str, robot_id: str) -> None:
        """Next 명령 처리 - l 방향 다음 노드로 전진"""
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found")
            return

        current_node = robot_state["current_node"]

        node_data = get_node(map_name, current_node)
        if not node_data:
            print(f"[Redis/Next] Node {current_node} not found")
            return

        next_node = node_data.get("l")
        if not next_node or next_node == 0:
            print(f"[Redis/Next] Robot {robot_id}: No left node available from node {current_node}")
            return

        robot_state_service.update_status(map_name, robot_id, RobotStatus.WORKING)

        print(f"[Redis/Next] Robot {robot_id}: {current_node} → {next_node}")

        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": f"{next_node}"})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: final_node {next_node} sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send (MQTT not connected)")

    def _handle_return_command(self, map_name: str, robot_id: str) -> None:
        """Return 명령 처리 - 로봇 상태를 RETURN으로 변경하고 복귀 노드 전송"""
        robot_state = robot_state_service.get_robot_state(map_name, robot_id)

        if not robot_state or "current_node" not in robot_state:
            print(f"[Redis] Robot {robot_id} state not found or missing current_node")
            return

        current_node = robot_state["current_node"]
        final_node = 0  # 로봇에 무조건 복귀하도록 하는 노드

        robot_state_service.update_position(map_name, robot_id, current_node, final_node)

        print(f"[Redis/Return] Robot {robot_id}: Return command executed (current: {current_node}, final_node: {final_node}, status: RETURN)")

        button_topic = f"{map_name}/{robot_id}/server/button"
        button_payload = json.dumps({"final_node": f"{final_node}"})

        if mqtt_service.publish(button_topic, button_payload):
            print(f"[Redis/Button] Robot {robot_id}: Return signal (final_node: {final_node}) sent to {button_topic}")
        else:
            print(f"[Redis/Button] Robot {robot_id}: Failed to send return signal (MQTT not connected)")


redis_command_handler = RedisCommandHandler()
