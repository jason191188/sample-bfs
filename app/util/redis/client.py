from typing import Optional

import redis

from app.config.settings import settings


class RedisService:
    def __init__(self):
        self.host = settings.redis.host
        self.port = settings.redis.port
        self.db = settings.redis.db
        self.client: redis.Redis = None

    def connect(self):
        try:
            self.client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
            self.client.ping()
            print("Redis 연결 성공")
        except Exception as e:
            print(f"Redis 연결 실패: {e}")
            self.client = None

    def disconnect(self):
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


redis_service = RedisService()
