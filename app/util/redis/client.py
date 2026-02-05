from typing import Optional, Callable
import threading

import redis

from app.config.settings import settings


class RedisService:
    def __init__(self):
        self.host = settings.redis.host
        self.port = settings.redis.port
        self.db = settings.redis.db
        self.client: redis.Redis = None
        self.pubsub: redis.client.PubSub = None
        self.pubsub_thread: threading.Thread = None

    def connect(self):
        try:
            self.client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
            self.client.ping()
            print("Redis 연결 성공")
        except Exception as e:
            print(f"Redis 연결 실패: {e}")
            self.client = None

    def disconnect(self):
        # Pub/Sub 스레드 먼저 중지
        if self.pubsub_thread:
            self.pubsub_thread.stop()
            self.pubsub_thread.join(timeout=5)

        # Pub/Sub 구독 해제 및 종료
        if self.pubsub:
            self.pubsub.unsubscribe()
            self.pubsub.close()

        # Redis 클라이언트 종료
        if self.client:
            self.client.close()

    def is_connected(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False

    # 기본 CRUD
    def get(self, key: str) -> Optional[str]:
        if self.client:
            return self.client.get(key)
        return None

    def set(self, key: str, value: str, ex: int = None) -> bool:
        if self.client:
            self.client.set(key, value, ex=ex)
            return True
        return False

    def delete(self, key: str) -> bool:
        if self.client:
            self.client.delete(key)
            return True
        return False

    # Hash 연산
    def hget(self, name: str, key: str) -> Optional[str]:
        if self.client:
            return self.client.hget(name, key)
        return None

    def hset(self, name: str, key: str, value: str) -> bool:
        if self.client:
            self.client.hset(name, key, value)
            return True
        return False

    def hgetall(self, name: str) -> dict:
        if self.client:
            return self.client.hgetall(name)
        return {}

    def hdel(self, name: str, key: str) -> bool:
        if self.client:
            self.client.hdel(name, key)
            return True
        return False

    def expire(self, key: str, seconds: int) -> bool:
        if self.client:
            self.client.expire(key, seconds)
            return True
        return False

    # Pub/Sub 기능
    def publish(self, channel: str, message: str) -> bool:
        """Redis 채널에 메시지 발행

        Args:
            channel: 채널 이름
            message: 발행할 메시지

        Returns:
            성공 여부
        """
        if self.client:
            self.client.publish(channel, message)
            print(f"Redis 채널에 메시지 발행: {channel} -> {message}")
            return True
        return False

    def subscribe(self, channel: str, handler: Callable[[str], None]) -> bool:
        """Redis 채널 구독 (별도 스레드에서 실행)

        Args:
            channel: 구독할 채널 이름
            handler: 메시지 수신 시 호출될 콜백 함수 (message: str)

        Returns:
            성공 여부
        """
        if not self.client:
            return False

        try:
            # PubSub 객체 생성 (재사용 또는 새로 생성)
            if not self.pubsub:
                self.pubsub = self.client.pubsub()

            # 채널 구독 및 핸들러 등록
            self.pubsub.subscribe(**{channel: lambda msg: handler(msg['data'])})

            # 이미 스레드가 실행 중이 아니면 새로 시작
            if not self.pubsub_thread or not self.pubsub_thread.is_alive():
                self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.01, daemon=True)

            print(f"Redis 채널 구독 시작: {channel}")
            return True
        except Exception as e:
            print(f"Redis 채널 구독 실패: {e}")
            return False

    def psubscribe(self, pattern: str, handler: Callable[[str, str], None]) -> bool:
        """Redis 채널 패턴 구독 (별도 스레드에서 실행)

        Args:
            pattern: 구독할 채널 패턴 (예: "robot:*")
            handler: 메시지 수신 시 호출될 콜백 함수 (channel: str, message: str)

        Returns:
            성공 여부
        """
        if not self.client:
            return False

        try:
            # PubSub 객체 생성 (재사용 또는 새로 생성)
            if not self.pubsub:
                self.pubsub = self.client.pubsub()

            # 패턴 구독 및 핸들러 등록
            self.pubsub.psubscribe(**{pattern: lambda msg: handler(msg['channel'], msg['data'])})

            # 이미 스레드가 실행 중이 아니면 새로 시작
            if not self.pubsub_thread or not self.pubsub_thread.is_alive():
                self.pubsub_thread = self.pubsub.run_in_thread(sleep_time=0.01, daemon=True)

            print(f"Redis 채널 패턴 구독 시작: {pattern}")
            return True
        except Exception as e:
            print(f"Redis 채널 패턴 구독 실패: {e}")
            return False

    def unsubscribe(self, channel: str = None) -> bool:
        """채널 구독 해제

        Args:
            channel: 구독 해제할 채널 (None이면 모든 채널)

        Returns:
            성공 여부
        """
        if self.pubsub:
            if channel:
                self.pubsub.unsubscribe(channel)
            else:
                self.pubsub.unsubscribe()
            return True
        return False


redis_service = RedisService()
