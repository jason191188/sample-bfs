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

    IDLE = "idle"          # 대기 중 (WAITING)
    MOVING = "moving"      # 이동 중 (WORKING, RETURN)
    ARRIVED = "arrived"    # 도착 완료 (DONE)
    CHARGING = "charging"  # 충전 중 (CHARGING)

    @staticmethod
    def from_robot_status(robot_status: "RobotStatus") -> "RobotOperationState | None":
        """RobotStatus에서 가동률 상태로 매핑

        Args:
            robot_status: Redis 저장용 로봇 상태

        Returns:
            RobotOperationState (ERROR 시 None 반환 → 가동률 누적 안함)
        """
        from app.domain.robot.robot_status import RobotStatus

        mapping = {
            RobotStatus.WORKING:  RobotOperationState.MOVING,
            RobotStatus.RETURN:   RobotOperationState.MOVING,
            RobotStatus.DONE:     RobotOperationState.ARRIVED,
            RobotStatus.CHARGING: RobotOperationState.CHARGING,
            RobotStatus.WAITING:  RobotOperationState.IDLE,
        }
        # ERROR는 가동률 누적하지 않음
        return mapping.get(robot_status)
