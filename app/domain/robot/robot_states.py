"""로봇 운영 상태 정의"""
from enum import Enum


class RobotOperationState(Enum):
    """로봇의 4가지 운영 상태"""

    WORKING = "working"  # 2번 노드에 있지 않은 시간 (작업 중)
    FULL_CHARGE_IDLE = "full_charge_idle"  # 2번 노드에서 충전 중 + 배터리 100% (완충 대기)
    CHARGING = "charging"  # 2번 노드에서 충전 중 + 배터리 100% 미만 (충전 중)
    IDLE = "idle"  # 2번 노드에서 충전 안하고 대기 중 (대기 중)

    @staticmethod
    def determine_state(current_node: int, charging_state: int, battery_state: float) -> "RobotOperationState":
        """로봇의 현재 상태를 판단

        Args:
            current_node: 현재 노드 번호
            charging_state: 충전 상태 (0: 미충전, 1: 충전중)
            battery_state: 배터리 잔량 (0-100)

        Returns:
            RobotOperationState
        """
        # 2번 노드에 있지 않으면 작업 중
        if current_node != 2:
            return RobotOperationState.WORKING

        # 2번 노드에 있을 때
        if charging_state == 1:
            # 충전 중
            if battery_state >= 100:
                return RobotOperationState.FULL_CHARGE_IDLE
            else:
                return RobotOperationState.CHARGING
        else:
            # 충전 안하고 대기
            return RobotOperationState.IDLE
