"""로봇 일일 운영 통계 서비스 - 4가지 상태별 시간 추적"""
from datetime import datetime, date, timedelta
from typing import Optional

from app.util.redis.client import redis_service
from app.domain.robot.robot_states import RobotOperationState


class DailyStatsService:
    """하루 단위로 로봇의 4가지 상태별 시간을 추적"""

    def _get_daily_stats_key(self, map_name: str, robot_id: str, target_date: date = None) -> str:
        """날짜별 통계 키 생성

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            target_date: 대상 날짜 (None이면 오늘)

        Returns:
            Redis 키 (예: "robot:daily_stats:map1:robot1:2024-01-27")
        """
        if target_date is None:
            target_date = date.today()
        date_str = target_date.isoformat()
        return f"robot:daily_stats:{map_name}:{robot_id}:{date_str}"

    def _get_current_state_key(self, map_name: str, robot_id: str) -> str:
        """현재 상태 추적 키 생성

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            Redis 키 (예: "robot:current_state:map1:robot1")
        """
        return f"robot:current_state:{map_name}:{robot_id}"

    def start_state(
        self,
        map_name: str,
        robot_id: str,
        new_state: RobotOperationState,
        timestamp: datetime = None
    ) -> None:
        """새로운 상태 시작 (이전 상태 종료 + 새 상태 시작)

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            new_state: 새로운 상태
            timestamp: 상태 변경 시간 (None이면 현재 시간)
        """
        if timestamp is None:
            timestamp = datetime.now()

        current_state_key = self._get_current_state_key(map_name, robot_id)

        # 현재 상태 조회
        current_state_data = redis_service.hgetall(current_state_key)

        # 이전 상태가 있으면 종료 처리
        if current_state_data and "state" in current_state_data and "started_at" in current_state_data:
            old_state = RobotOperationState(current_state_data["state"])
            started_at = datetime.fromisoformat(current_state_data["started_at"])

            # 00시 경계를 기준으로 날짜별로 분할 처리
            self._split_and_add_duration(map_name, robot_id, old_state, started_at, timestamp)

        # 새로운 상태 시작
        redis_service.hset(current_state_key, "state", new_state.value)
        redis_service.hset(current_state_key, "started_at", timestamp.isoformat())

        print(f"[DailyStats] Robot {robot_id}: {new_state.value} started")

    def _split_and_add_duration(
        self,
        map_name: str,
        robot_id: str,
        state: RobotOperationState,
        started_at: datetime,
        ended_at: datetime
    ) -> None:
        """날짜 경계를 기준으로 시간을 분할하여 각 날짜에 누적

        정상적으로는 매일 00시에 스케줄러가 상태를 초기화하므로,
        같은 날짜만 처리하면 되지만, 서버 다운 등의 예외 상황을 대비하여
        여러 날을 걸치는 경우도 처리합니다.

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            state: 상태
            started_at: 시작 시간
            ended_at: 종료 시간
        """
        start_date = started_at.date()
        end_date = ended_at.date()

        # 같은 날짜면 그냥 추가 (일반적인 경우)
        if start_date == end_date:
            duration = (ended_at - started_at).total_seconds()
            self._add_duration(map_name, robot_id, state, duration, start_date)
            print(f"[DailyStats] Robot {robot_id}: {state.value} ended (duration: {duration:.1f}s on {start_date})")
            return

        # 날짜가 다르면 각 날짜별로 분할 (00시 초기화 실패 시 백업)
        print(f"[DailyStats] WARNING: Robot {robot_id} state spans multiple days ({start_date} to {end_date}). Daily reset may have failed.")
        current_date = start_date
        current_time = started_at

        while current_date <= end_date:
            # 현재 날짜의 마지막 시간 (23:59:59.999999)
            end_of_day = datetime.combine(current_date, datetime.max.time())

            # 현재 구간의 종료 시간 결정
            if current_date == end_date:
                segment_end = ended_at
            else:
                segment_end = end_of_day

            # 현재 날짜 구간의 시간 계산 및 저장
            duration = (segment_end - current_time).total_seconds()
            self._add_duration(map_name, robot_id, state, duration, current_date)
            print(f"[DailyStats] Robot {robot_id}: {state.value} segment (duration: {duration:.1f}s on {current_date})")

            # 다음 날짜로 이동
            current_date = current_date + timedelta(days=1)
            current_time = datetime.combine(current_date, datetime.min.time())

    def _add_duration(
        self,
        map_name: str,
        robot_id: str,
        state: RobotOperationState,
        duration: float,
        target_date: date = None
    ) -> None:
        """특정 상태의 누적 시간 추가

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            state: 상태
            duration: 추가할 시간 (초)
            target_date: 대상 날짜 (None이면 오늘)
        """
        stats_key = self._get_daily_stats_key(map_name, robot_id, target_date)
        field = state.value

        # 기존 누적 시간 조회
        current_duration = redis_service.hget(stats_key, field)
        current_duration = float(current_duration) if current_duration else 0.0

        # 누적 시간 업데이트
        new_duration = current_duration + duration
        redis_service.hset(stats_key, field, str(new_duration))

        # 통계 키 만료 시간 설정 (30일)
        redis_service.expire(stats_key, 30 * 24 * 60 * 60)

    def get_daily_stats(
        self,
        map_name: str,
        robot_id: str,
        target_date: date = None
    ) -> dict[str, float]:
        """일일 통계 조회

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            target_date: 대상 날짜 (None이면 오늘)

        Returns:
            {상태명: 시간(초)} 딕셔너리
        """
        stats_key = self._get_daily_stats_key(map_name, robot_id, target_date)
        stats = redis_service.hgetall(stats_key)

        # 현재 진행 중인 상태의 시간도 포함
        current_state_key = self._get_current_state_key(map_name, robot_id)
        current_state_data = redis_service.hgetall(current_state_key)

        result = {
            "working": 0.0,
            "full_charge_idle": 0.0,
            "charging": 0.0,
            "idle": 0.0
        }

        # Redis에 저장된 누적 시간
        for state_value in result.keys():
            if state_value in stats:
                result[state_value] = float(stats[state_value])

        # 현재 진행 중인 상태의 시간 추가 (같은 날짜인 경우만)
        if current_state_data and "state" in current_state_data and "started_at" in current_state_data:
            started_at = datetime.fromisoformat(current_state_data["started_at"])
            if target_date is None or started_at.date() == target_date:
                current_state = current_state_data["state"]
                ongoing_duration = (datetime.now() - started_at).total_seconds()
                result[current_state] = result.get(current_state, 0.0) + ongoing_duration

        return result

    def get_daily_stats_formatted(
        self,
        map_name: str,
        robot_id: str,
        target_date: date = None
    ) -> dict:
        """일일 통계 조회 (시간 형식 포함)

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            target_date: 대상 날짜 (None이면 오늘)

        Returns:
            통계 딕셔너리 (초, 분, 시간, 퍼센트 포함)
        """
        stats = self.get_daily_stats(map_name, robot_id, target_date)

        total_seconds = sum(stats.values())
        total_hours = total_seconds / 3600

        result = {
            "date": (target_date or date.today()).isoformat(),
            "total_seconds": total_seconds,
            "total_hours": round(total_hours, 2),
            "states": {}
        }

        for state_name, seconds in stats.items():
            hours = seconds / 3600
            minutes = seconds / 60
            percentage = (seconds / total_seconds * 100) if total_seconds > 0 else 0

            result["states"][state_name] = {
                "seconds": round(seconds, 1),
                "minutes": round(minutes, 1),
                "hours": round(hours, 2),
                "percentage": round(percentage, 1)
            }

        return result

    def get_current_state(self, map_name: str, robot_id: str) -> Optional[dict]:
        """현재 진행 중인 상태 조회

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            {state, started_at, duration} 또는 None
        """
        current_state_key = self._get_current_state_key(map_name, robot_id)
        current_state_data = redis_service.hgetall(current_state_key)

        if not current_state_data or "state" not in current_state_data:
            return None

        started_at = datetime.fromisoformat(current_state_data["started_at"])
        duration = (datetime.now() - started_at).total_seconds()

        return {
            "state": current_state_data["state"],
            "started_at": current_state_data["started_at"],
            "duration_seconds": round(duration, 1)
        }


daily_stats_service = DailyStatsService()
