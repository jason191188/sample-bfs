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
            # 복귀 시그널 → 바로 2번 노드로 이동
            return 2, True
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

        # Redis에 로봇 상태 저장 (도착)
        robot_state_service.update_status(map_name, robot_id, "arrived", data.current_node)

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
        # 해당 노드가 이 로봇이 점유한 노드인지 확인 후 해제
        success = release_node(map_name, data.current_node, robot_id)
        if success:
            print(f"[Remove] Robot {robot_id} released node {data.current_node}.")
        else:
            print(f"[Remove] Failed to release node {data.current_node} for robot {robot_id}.")
