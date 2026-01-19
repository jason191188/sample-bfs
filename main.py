from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.domain.health import router as health_router
from app.domain.path import router as path_router
from app.util.mqtt.client import mqtt_service
from app.util.mqtt.handlers import CommandHandler, StatusHandler
from app.util.redis.client import redis_service
from app.util.redis.init_data import init_node_data


def register_mqtt_handlers():
    """MQTT 핸들러 등록"""
    mqtt_service.register_handler(CommandHandler())
    mqtt_service.register_handler(StatusHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_mqtt_handlers()
    mqtt_service.connect()
    redis_service.connect()
    init_node_data()
    yield
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
