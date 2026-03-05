import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.client import mqtt_service
from app.util.mqtt.handlers.models import (
    PathPayload,
    BatteryPayload,
    ArrivePayload,
    RemovePathPayload,
)
from app.util.redis.init_data import release_node, release_robot_nodes
from app.util.redis.client import redis_service
from app.domain.path.path_service import path_calculation_service
from app.domain.robot.robot_state_service import robot_state_service
from app.domain.robot.robot_status import RobotStatus
from app.util.validators import MapNameValidator


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

        # 맵 이름 검증
        if not MapNameValidator.validate_silent(map_name):
            print(f"[MQTT] Invalid map name: {map_name}. Must start with 'smartfarm_'. Ignoring message.")
            return

        if command == "path_plan":
            self._handle_path(map_name, robot_id, payload)
        elif command == "battery":
            self._handle_battery(map_name, robot_id, payload)
        elif command == "arrive":
            self._handle_arrive(map_name, robot_id, payload)
        elif command == "remove_path":
            self._handle_remove(map_name, robot_id, payload)
        elif command == "robot_error":
            self._handle_error(map_name, robot_id, payload)

    def _determine_destination(self, final_node: int) -> tuple[int, bool]:
        """목적지 결정 (복귀 로직)

        Args:
            final_node: 요청된 목적지 (0이면 복귀 시그널)

        Returns:
            (실제 목적지, 복귀 여부)
        """
        if final_node == 0:
            # 복귀 시그널 → 1번 노드(충전소)로 이동
            return 1, True
        else:
            # 일반 경로 요청
            return final_node, False

    def _handle_path(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 계산 요청 처리 - BFS로 경로 계산 후 MQTT로 응답"""
        data = PathPayload(**json.loads(payload))

        # 목적지 결정 (복귀 로직 처리)
        destination, is_return = self._determine_destination(data.final_node)

        # finalNode를 Redis에 저장 (NEXT 명령에서 방향 결정에 사용)
        robot_key = f"robot:state:{map_name}:{robot_id}"
        redis_service.hset(robot_key, "final_node", str(destination))

        if is_return:
            print(f"[Path] Robot {robot_id}: Return signal detected (node {data.current_node} → {destination})")
        else:
            print(f"[Path] Robot {robot_id}: Path request (node {data.current_node} → {destination})")

        path_calculation_service.calculate_and_send_path(map_name, robot_id, data.current_node, destination, is_return)

    def _handle_battery(self, map_name: str, robot_id: str, payload: str) -> None:
        """배터리 상태 처리 - Redis에 저장"""
        data = BatteryPayload(**json.loads(payload))

        # 전압을 퍼센트로 변환
        battery_percent = self._calculate_battery_percent(
            float(data.battery_state),
            data.battery_charging_state
        )

        # Redis에 배터리 정보 저장
        robot_state_service.update_battery(map_name, robot_id, battery_percent, data.battery_charging_state)
        print(f"[Battery] Robot {robot_id}: Battery {battery_percent}% (voltage: {data.battery_state}V, charging: {data.battery_charging_state})")

    def _calculate_battery_percent(self, input_volt: float, charging_state: int) -> int:
        """배터리 전압을 퍼센트로 변환"""
        max_volt = 16.5
        min_volt = 13.5

        # 충전 상수 (충전 중일 때 전압 보정)
        charging_constant = (max_volt - input_volt) * 0.07

        # 충전 중이면 충전 상수 적용
        if charging_state == 1:
            input_volt -= charging_constant

        # 퍼센트 계산
        battery_percent = round((input_volt - min_volt) / (max_volt - min_volt) * 100)

        # 0~100 범위로 제한
        return max(0, min(100, battery_percent))

    def _handle_arrive(self, map_name: str, robot_id: str, payload: str) -> None:
        """로봇 도착 처리 - 해당 로봇이 점유한 모든 노드 해제"""
        data = ArrivePayload(**json.loads(payload))

        # Redis에 current_node 업데이트 (도착한 노드로 위치 변경)
        robot_state_service.update_position(map_name, robot_id, data.current_node)

        # 도착 키를 별도로 저장하고 3분(180초) 후 만료
        arrive_key = f"robot:arrive:{map_name}:{robot_id}"
        redis_service.set(arrive_key, str(data.current_node), ex=180)

        # 해당 로봇이 점유한 모든 노드 해제
        released_count = release_robot_nodes(map_name, robot_id)
        print(f"[Arrive] Robot {robot_id} arrived at node {data.current_node}. Released {released_count} nodes.")

        # 도착 확인 응답 전송
        response_topic = f"{map_name}/{robot_id}/server/arrive"
        response_payload = json.dumps({"yes_or_no": "yes"})
        mqtt_service.publish(response_topic, response_payload)

    def _handle_remove(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 노드 해제 - 특정 노드의 점유 해제"""
        data = RemovePathPayload(**json.loads(payload))

        robot_state_service.update_position(map_name, robot_id, data.current_node)

        # 해당 노드가 이 로봇이 점유한 노드인지 확인 후 해제
        success = release_node(map_name, data.current_node, robot_id)
        if success:
            print(f"[Remove] Robot {robot_id} released node {data.current_node}.")
        else:
            print(f"[Remove] Failed to release node {data.current_node} for robot {robot_id}.")

        path_key = f"robot:path:{map_name}:{robot_id}"
        is_return_str = redis_service.hget(path_key, "is_return")

        # 경로 주행 순서 검증 + 실제 이동 노드 수 확정
        nodes_traversed = 1  # 기본값
        path_nodes_str = redis_service.hget(path_key, "path_nodes")
        path_index_str = redis_service.hget(path_key, "path_index")
        if path_nodes_str and path_index_str is not None:
            path_nodes = [int(n) for n in path_nodes_str.split(",")]
            path_index = int(path_index_str)
            if path_index < len(path_nodes):
                expected = path_nodes[path_index]
                if data.current_node == expected:
                    nodes_traversed = 1
                    redis_service.hset(path_key, "path_index", str(path_index + 1))
                    print(f"[Remove] Robot {robot_id}: path OK [{path_index + 1}/{len(path_nodes)}] node {data.current_node}")
                elif data.current_node in path_nodes[path_index:]:
                    new_index = path_nodes.index(data.current_node, path_index) + 1
                    nodes_traversed = new_index - path_index
                    redis_service.hset(path_key, "path_index", str(new_index))
                    print(f"[Remove] Robot {robot_id}: path WARNING - skipped {nodes_traversed - 1} node(s), expected {expected} got {data.current_node} [{new_index}/{len(path_nodes)}]")
                else:
                    print(f"[Remove] Robot {robot_id}: path ERROR - unexpected node {data.current_node}, expected {expected} [{path_index}/{len(path_nodes)}]")

        # 실제 이동 노드 수 × 배율(전진×1, 복귀×3)로 node_count 누적
        unit = 3 if is_return_str == "True" else 1
        increment = nodes_traversed * unit
        current_state_key = f"robot:current_state:{map_name}:{robot_id}"
        current_count_str = redis_service.hget(current_state_key, "node_count")
        current_count = int(current_count_str) if current_count_str else 0
        new_count = current_count + increment
        redis_service.hset(current_state_key, "node_count", str(new_count))
        print(f"[Remove] Robot {robot_id}: node_count +{increment} ({nodes_traversed} node(s) × {unit}, total: {new_count})")

        # Redis로 remove 정보 publish
        payload_data = json.loads(payload)
        if "final_node" in payload_data:
            del payload_data["final_node"]
        message = json.dumps({
            "type": "REMOVE",
            "payload": payload_data
        })
        redis_service.publish("smartfarm:robot", message)

    def _handle_error(self, map_name: str, robot_id: str, payload: str) -> None:
        """로봇 에러 처리 - 상태를 ERROR로 변경하고 Redis로 에러 정보 publish"""
        # 로봇 상태를 ERROR로 변경
        robot_state_service.update_status(map_name, robot_id, RobotStatus.ERROR)

        # Redis로 에러 정보 publish
        message = json.dumps({
            "type": "ERROR",
            "payload": json.loads(payload)
        })
        redis_service.publish("smartfarm:robot", message)
        print(f"[Error] Robot {robot_id}: {payload}")
