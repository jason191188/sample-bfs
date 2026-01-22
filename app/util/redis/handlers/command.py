import json

from app.domain.path.path_service import path_calculation_service


class RedisCommandHandler:
    """Redis Pub/Sub 명령 핸들러 - PathCalculationService 사용"""

    def handle_message(self, message: str) -> None:
        """Redis 채널 메시지 처리

        Args:
            message: JSON 형식의 메시지 (type, mapName, robotId 포함)
        """
        try:
            data = json.loads(message)
            command_type = data.get("type")
            map_name = data.get("mapName")
            robot_id = data.get("robotId")

            if not all([command_type, map_name, robot_id]):
                print(f"[Redis] Missing required fields: type, mapName, or robotId")
                return

            if command_type == "start":
                self._handle_start_command(data, map_name, robot_id)
            elif command_type == "return":
                self._handle_return_command(data, map_name, robot_id)
            else:
                print(f"[Redis] Unknown command type: {command_type} (only 'start' and 'return' are supported)")

        except json.JSONDecodeError as e:
            print(f"[Redis] Invalid JSON message: {e}")
        except Exception as e:
            print(f"[Redis] Error handling message: {e}")

    def _handle_start_command(self, data: dict, map_name: str, robot_id: str) -> None:
        """Start 명령 처리 - PathCalculationService 사용"""
        current_node = data.get("currentNode")
        final_node = data.get("finalNode")

        if current_node is None or final_node is None:
            print("[Redis] Missing currentNode or finalNode for start command")
            return

        print(f"[Redis/Path] Robot {robot_id}: Start request (node {current_node} → {final_node})")

        # PathCalculationService를 사용하여 경로 계산 및 응답
        path_calculation_service.calculate_and_send_path(map_name, robot_id, current_node, final_node, is_return=False)

    def _handle_return_command(self, data: dict, map_name: str, robot_id: str) -> None:
        """Return 명령 처리 - PathCalculationService 사용"""
        current_node = data.get("currentNode")

        if current_node is None:
            print("[Redis] Missing currentNode for return command")
            return

        # 복귀 목적지 결정
        destination = 2 if current_node == 1 else 1
        print(f"[Redis/Path] Robot {robot_id}: Return request (node {current_node} → {destination})")

        # PathCalculationService를 사용하여 경로 계산 및 응답
        path_calculation_service.calculate_and_send_path(map_name, robot_id, current_node, destination, is_return=True)


redis_command_handler = RedisCommandHandler()
