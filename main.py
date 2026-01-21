from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.domain.health import router as health_router
from app.domain.path import router as path_router
from app.domain.redis_command import router as redis_command_router
from app.util.mqtt.client import mqtt_service
from app.util.mqtt.handlers import CommandHandler, StatusHandler
from app.util.redis.client import redis_service
from app.util.redis.init_data import init_node_data
from app.util.redis.handlers.command import redis_command_handler

""" TODO: 
        - domain/path에 경로 계산 함수를 구현한 클래스를 만들어서 핸들러에서 사용
        - 초기 데이터에 mapName을 기준으로 노드 데이터 저장
        - 레디스에 로봇 정보 데이터 저장 및 관리
        - 도커파일 및 도커 컴포즈 설정
        - 

"""

def register_mqtt_handlers():
    """MQTT 핸들러 등록"""
    mqtt_service.register_handler(CommandHandler())
    mqtt_service.register_handler(StatusHandler())


def register_redis_handlers():
    """Redis Pub/Sub 핸들러 등록"""
    # 로봇 명령 채널 구독 (단일 채널)
    redis_service.subscribe("robot:command", redis_command_handler.handle_message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MQTT 연결 및 핸들러 등록
    register_mqtt_handlers()
    mqtt_service.connect()

    # Redis 연결 및 핸들러 등록
    redis_service.connect()
    init_node_data()
    register_redis_handlers()

    yield

    # 종료 시 연결 해제
    mqtt_service.disconnect()
    redis_service.disconnect()


app = FastAPI(
    title="Robot Controller API",
    description="로봇 컨트롤러 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(path_router.router)
app.include_router(redis_command_router.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
