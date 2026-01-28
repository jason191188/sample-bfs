"""APScheduler를 사용한 스케줄러 설정"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from app.util.redis.client import redis_service
from app.domain.robot.robot_states import RobotOperationState
from app.domain.robot.daily_stats_service import daily_stats_service


class DailyResetScheduler:
    """매일 00시 로봇 상태 자동 초기화 스케줄러"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self):
        """스케줄러 시작"""
        # 매일 00:00:00에 실행
        self.scheduler.add_job(
            self.reset_all_robots,
            trigger=CronTrigger(hour=0, minute=0, second=0),
            id="daily_robot_reset",
            name="Daily Robot State Reset at Midnight",
            replace_existing=True
        )
        self.scheduler.start()
        print("[Scheduler] Daily reset scheduler started (triggers at 00:00:00)")

    def stop(self):
        """스케줄러 종료"""
        self.scheduler.shutdown()
        print("[Scheduler] Scheduler stopped")

    def reset_all_robots(self):
        """모든 로봇의 현재 상태를 종료하고 즉시 재시작"""
        print(f"[Scheduler] Daily reset started at {datetime.now()}")

        # Redis에서 모든 로봇의 현재 상태 키 조회
        pattern = "robot:current_state:*"
        keys = redis_service.keys(pattern)

        reset_count = 0
        for key in keys:
            try:
                # 키 파싱: robot:current_state:{map_name}:{robot_id}
                parts = key.split(":")
                if len(parts) != 4:
                    continue

                map_name = parts[2]
                robot_id = parts[3]

                # 현재 상태 조회
                current_state_data = redis_service.hgetall(key)
                if not current_state_data or "state" not in current_state_data:
                    continue

                state = RobotOperationState(current_state_data["state"])

                # 현재 상태를 종료하고 즉시 재시작
                # (start_state가 자동으로 이전 상태 종료 처리)
                daily_stats_service.start_state(map_name, robot_id, state, datetime.now())

                reset_count += 1
                print(f"[Scheduler] Reset {map_name}/{robot_id}: {state.value}")

            except Exception as e:
                print(f"[Scheduler] Error resetting {key}: {e}")

        print(f"[Scheduler] Daily reset completed: {reset_count} robots reset")


# 전역 스케줄러 인스턴스
daily_reset_scheduler = DailyResetScheduler()
