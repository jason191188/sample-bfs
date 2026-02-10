"""로봇 가동률 계산용 상태 정의"""
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.robot.robot_status import RobotStatus


class RobotOperationState(Enum):
    """로봇의 4가지 가동률 계산용 상태

    RobotStatus (Redis 저장용 6가지)와는 독립적으로 관리됩니다.
    RobotStatus가 저장된 후, from_robot_status()로 매핑하여 사용합니다.
    """

    IDLE = "idle"                        # 대기 중, 배터리 100 미만 (WAITING/DONE + battery < 100)
    WORKING = "working"                  # 작업 중 (WORKING, RETURN)
    FULL_CHARGE_IDLE = "full_charge_idle"  # 완충 대기 중 (WAITING/DONE + battery >= 100)
    CHARGING = "charging"                # 충전 중 (CHARGING)

    @staticmethod
    def from_robot_status(robot_status: "RobotStatus", battery_state: float = 0) -> "RobotOperationState | None":
        """RobotStatus와 배터리 상태에서 가동률 상태로 매핑

        Args:
            robot_status: Redis 저장용 로봇 상태
            battery_state: 배터리 잔량 (%)

        Returns:
            RobotOperationState (ERROR 시 None 반환 → 가동률 누적 안함)
        """
        from app.domain.robot.robot_status import RobotStatus

        # 작업 중
        if robot_status in (RobotStatus.WORKING, RobotStatus.RETURN):
            return RobotOperationState.WORKING

        # 충전 중
        if robot_status == RobotStatus.CHARGING:
            return RobotOperationState.CHARGING

        # 대기/도착 상태 → 배터리 레벨로 구분
        if robot_status in (RobotStatus.WAITING, RobotStatus.DONE):
            if battery_state >= 100:
                return RobotOperationState.FULL_CHARGE_IDLE
            else:
                return RobotOperationState.IDLE

        # ERROR는 가동률 누적하지 않음
        return None
