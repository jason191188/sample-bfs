import uuid
from pydantic_settings import BaseSettings


class MQTTSettings(BaseSettings):
    broker: str = "54.180.116.81"
    port: int = 1883
    client_id: str = f"smartFarmSub-{uuid.uuid4()}"
    class Config:
        env_prefix = "MQTT_"


class RedisSettings(BaseSettings):
    host: str = "localhost"  # Docker 컨테이너명 (로컬 개발 시 환경변수로 "localhost" 오버라이드)
    port: int = 6379
    db: int = 0

    class Config:
        env_prefix = "REDIS_"


class Settings(BaseSettings):
    app_name: str = "Robot Controller API"
    version: str = "1.0.0"

    mqtt: MQTTSettings = MQTTSettings()
    redis: RedisSettings = RedisSettings()


settings = Settings()
