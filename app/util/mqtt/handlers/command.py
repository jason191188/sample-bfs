import json

from app.util.mqtt.handler import MQTTHandler
from app.util.mqtt.client import mqtt_service
from app.util.mqtt.handlers.models import (
    PathPayload,
    BatteryPayload,
    ArrivePayload,
    RemovePathPayload,
    NextPayload,
)
from app.util.redis.init_data import release_node, release_robot_nodes, get_node
from app.util.redis.client import redis_service
from app.domain.path.service import bfs
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
        elif command == "next":
            self._handle_next(map_name, robot_id, payload)

    def _parse_node(self, node_str: str) -> tuple[int, int | None]:
        """노드 문자열을 파싱하여 (노드ID, 서브포지션) 반환

        Args:
            node_str: "2" 또는 "2-1" 형태의 노드 문자열

        Returns:
            (node_id, sub_position) - 서브포지션이 없으면 None
        """
        if "-" in node_str:
            parts = node_str.split("-")
            return int(parts[0]), int(parts[1])
        else:
            return int(node_str), None

    def _determine_destination(self, current_node: int, final_node: int) -> tuple[int, bool]:
        """목적지 결정 (복귀 로직)

        Args:
            current_node: 현재 노드
            final_node: 요청된 목적지 (0 또는 2이면 복귀 시그널)

        Returns:
            (실제 목적지, 복귀 여부)
        """
        if final_node == 0 or final_node == 2:
            # 복귀 시그널 → 바로 2번 노드로 이동
            return 2, True
        else:
            # 일반 경로 요청
            return final_node, False

    def _handle_path(self, map_name: str, robot_id: str, payload: str) -> None:
        """경로 계산 요청 처리 - BFS로 경로 계산 후 MQTT로 응답"""
        data = PathPayload(**json.loads(payload))

        # 서브노드 요청 감지 (final_node에 "-"가 포함된 경우: "2-1" 형태)
        if "-" in data.final_node:
            self._handle_sub_node_path(map_name, robot_id, data)
            return

        # current_node 파싱 (서브포지션은 일반 경로에서는 무시)
        current_node_id, _ = self._parse_node(data.current_node)

        # 일반 경로 요청
        final_node = int(data.final_node)

        # 목적지 결정 (복귀 로직 처리)
        destination, is_return = self._determine_destination(current_node_id, final_node)

        if is_return:
            print(f"[Path] Robot {robot_id}: Return signal detected (node {current_node_id} → {destination})")
        else:
            print(f"[Path] Robot {robot_id}: Path request (node {current_node_id} → {destination})")

        # Redis에 로봇 위치 정보 저장 (is_return 플래그 전달)
        robot_state_service.update_position(map_name, robot_id, current_node_id, destination, is_return)

        # PathCalculationService를 사용하여 경로 계산 및 응답 (원본 current_node 문자열 전달)
        start_display = data.current_node if "-" in data.current_node else None
        path_calculation_service.calculate_and_send_path(map_name, robot_id, current_node_id, destination, is_return, start_display)

    def _handle_sub_node_path(self, map_name: str, robot_id: str, data) -> None:
        """서브노드 경로 요청 처리 (final_node가 "2-1" 형태)"""
        parts = data.final_node.split("-")
        target_node = int(parts[0])
        target_sub = int(parts[1])
        current_node, current_node_sub = self._parse_node(data.current_node)

        # 방향 결정
        if current_node != target_node:
            # 다른 노드로 이동: 현재 노드에서 목표 노드 방향 찾기
            node_data = get_node(map_name, current_node)
            if not node_data:
                print(f"[Next] Robot {robot_id}: Node {current_node} not found")
                return
            direction = None
            for d in ["l", "r", "u", "d"]:
                if node_data.get(d) == target_node:
                    direction = d
                    break
            if not direction:
                print(f"[Next] Robot {robot_id}: Node {target_node} not adjacent to {current_node}")
                return
        else:
            # 같은 노드 내 이동: 저장된 최종 목적지로 BFS하여 방향 결정
            state = robot_state_service.get_robot_state(map_name, robot_id)
            stored_final = state.get("final_node") if state else None

            if stored_final and stored_final != current_node:
                _, directions = bfs(map_name, current_node, stored_final)
                direction = directions[0] if directions else None
            else:
                direction = None

            if not direction:
                # Fallback: 노드의 첫 번째 유효 방향
                node_data = get_node(map_name, current_node)
                if node_data:
                    for d in ["l", "r", "u", "d"]:
                        if node_data.get(d, 0) != 0:
                            direction = d
                            break
                if not direction:
                    direction = "l"

        # 현재 서브포지션 결정
        if current_node_sub is not None:
            current_sub = current_node_sub
        elif current_node == target_node:
            current_sub = target_sub - 1  # 같은 노드: 한 칸 이전
        else:
            current_sub = 4  # 다른 노드: 이전 노드 끝

        # 응답 생성
        path_str = f"{target_node}/{direction}~{target_node}-{target_sub}!{current_node}-{current_sub},{direction}/"
        response_topic = f"{map_name}/{robot_id}/server/path_plan"
        response_payload = json.dumps({"path": path_str})
        mqtt_service.publish(response_topic, response_payload)
        print(f"[Next] Robot {robot_id}: {current_node}-{current_sub} → {target_node}-{target_sub} (direction: {direction})")

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

        # current_node 파싱 (노드 ID만 사용)
        current_node_id, _ = self._parse_node(data.current_node)

        # Redis에 로봇 상태 저장 (도착 - DONE)
        robot_state_service.update_status(map_name, robot_id, RobotStatus.DONE, current_node_id)

        # 도착 키를 별도로 저장하고 3분(180초) 후 만료
        arrive_key = f"robot:arrive:{map_name}:{robot_id}"
        redis_service.set(arrive_key, str(current_node_id), ex=180)

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

        # current_node 파싱 (노드 ID만 사용)
        current_node_id, _ = self._parse_node(data.current_node)

        # 해당 노드가 이 로봇이 점유한 노드인지 확인 후 해제
        success = release_node(map_name, current_node_id, robot_id)
        if success:
            print(f"[Remove] Robot {robot_id} released node {current_node_id}.")
        else:
            print(f"[Remove] Failed to release node {current_node_id} for robot {robot_id}.")

        # Redis로 remove 정보 publish
        message = json.dumps({
            "type": "REMOVE",
            "payload": json.loads(payload)
        })
        redis_service.publish("smartfarm::robot", message)

    def _handle_next(self, map_name: str, robot_id: str, payload: str) -> None:
        """한 칸 전진 처리

        sub_position 있는 경우: 서브노드 단위 이동 (0~3: 같은 노드, 4: 다음 노드)
        sub_position 없는 경우: 노드 단위 이동 (다음 노드로 이동)
        """
        data = NextPayload(**json.loads(payload))

        # current_node 파싱
        current_node_id, current_node_sub = self._parse_node(data.current_node)

        if data.sub_position is not None:
            # 서브포지션 포함 모드
            if data.sub_position < 4:
                next_node = current_node_id
                next_sub = data.sub_position + 1
            else:
                node = get_node(map_name, current_node_id)
                if not node:
                    print(f"[Next] Robot {robot_id}: Node {current_node_id} not found")
                    return
                next_node_id = node.get(data.direction, 0)
                if next_node_id == 0:
                    print(f"[Next] Robot {robot_id}: No node in direction '{data.direction}' from node {current_node_id}")
                    return
                next_node = next_node_id
                next_sub = 0

            path_str = f"{next_node}/{data.direction}~{next_node}-{next_sub}!{current_node_id}-{data.sub_position},{data.direction}/"
            log_msg = f"{current_node_id}-{data.sub_position} → {next_node}-{next_sub}"
        else:
            # 노드 단위 모드
            node = get_node(map_name, current_node_id)
            if not node:
                print(f"[Next] Robot {robot_id}: Node {current_node_id} not found")
                return
            next_node_id = node.get(data.direction, 0)
            if next_node_id == 0:
                print(f"[Next] Robot {robot_id}: No node in direction '{data.direction}' from node {current_node_id}")
                return
            next_node = next_node_id

            path_str = f"{next_node}/{data.direction}~{next_node}!{current_node_id},{data.direction}/"
            log_msg = f"{current_node_id} → {next_node}"

        response_topic = f"{map_name}/{robot_id}/server/path_plan"
        response_payload = json.dumps({"path": path_str})
        mqtt_service.publish(response_topic, response_payload)
        print(f"[Next] Robot {robot_id}: {log_msg}")

    def _handle_error(self, map_name: str, robot_id: str, payload: str) -> None:
        """로봇 에러 처리 - 상태를 ERROR로 변경하고 Redis로 에러 정보 publish"""
        # 로봇 상태를 ERROR로 변경
        robot_state_service.update_status(map_name, robot_id, RobotStatus.ERROR)

        # Redis로 에러 정보 publish
        message = json.dumps({
            "type": "ERROR",
            "payload": json.loads(payload)
        })
        redis_service.publish("smartfarm::robot", message)
        print(f"[Error] Robot {robot_id}: {payload}")
