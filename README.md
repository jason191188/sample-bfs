# Robot Controller API

로봇 컨트롤러 API 서버 (FastAPI + MQTT + Redis)

## 요구사항

- Python 3.10+
- Redis 서버
- MQTT 브로커

## 설치

```bash
# 가상환경 생성 및 활성화
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

## 환경 변수 설정 (선택사항)

기본값이 설정되어 있으며, 필요시 환경변수로 오버라이드 가능합니다.

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `MQTT_BROKER` | mqtt.hprobot.cloud | MQTT 브로커 주소 |
| `MQTT_PORT` | 1883 | MQTT 포트 |
| `REDIS_HOST` | 192.168.0.75 | Redis 호스트 |
| `REDIS_PORT` | 6379 | Redis 포트 |
| `REDIS_DB` | 0 | Redis DB 번호 |

## 실행 방법

### 1. 직접 실행 (개발용)

```bash
python main.py
```

### 2. uvicorn CLI 실행

```bash
# 기본 실행
uvicorn main:app --host 0.0.0.0 --port 8000

# 개발 모드 (자동 리로드)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 워커 수 지정 (프로덕션)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--host` | 바인딩할 호스트 주소 (기본: 127.0.0.1) |
| `--port` | 포트 번호 (기본: 8000) |
| `--reload` | 코드 변경 시 자동 재시작 (개발용) |
| `--workers` | 워커 프로세스 수 (프로덕션용) |
| `--log-level` | 로그 레벨 (debug, info, warning, error, critical) |

## API 문서

서버 실행 후 아래 URL에서 API 문서를 확인할 수 있습니다.

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
