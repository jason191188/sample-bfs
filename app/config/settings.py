from pydantic_settings import BaseSettings


class MQTTSettings(BaseSettings):
    broker: str = "dev-mqtt.hprobot.cloud"
    port: int = 1883
    pub_topic: str = "robot/path"
    sub_topic: str = "robot/command"

    class Config:
        env_prefix = "MQTT_"


class RedisSettings(BaseSettings):
    host: str = "localhost"
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
