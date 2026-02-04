"""로봇 상태 정의 (Redis 저장용)"""
from enum import Enum


class RobotStatus(Enum):
    """로봇의 6가지 운영 상태 (Redis status 필드에 저장)

    가동률 계산용 RobotOperationState와는 독립적으로 관리됩니다.
    저장된 후 RobotOperationState.from_robot_status()로 가동률 상태로 변환됩니다.
    """

    WORKING = "WORKING"      # 작업 중 (이동 또는 서빙)
    RETURN = "RETURN"        # 복귀 중 (2번 노드로 이동)
    WAITING = "WAITING"      # 대기 중 (2번 노드에서 대기)
    DONE = "DONE"            # 작업 완료 (도착)
    CHARGING = "CHARGING"    # 충전 중
    ERROR = "ERROR"          # 에러 상태
