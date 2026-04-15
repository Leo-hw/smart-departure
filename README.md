# smart-departure

Google Calendar 일정과 지도 API를 기반으로 출발 시각을 계산해 텔레그램으로 알림을 보내는 Railway cron worker입니다.

## Requirements

- Python 3.11+
- 필수 환경변수
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_CALENDAR_IDS`
  - `GOOGLE_MAPS_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `HOME_ADDRESS`

## Local Run

1. 가상환경을 생성하고 활성화합니다.
2. 의존성을 설치합니다.
3. 환경변수를 설정합니다.
4. 엔트리포인트를 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account"}'
export GOOGLE_CALENDAR_IDS='primary'
export GOOGLE_MAPS_API_KEY='your-google-maps-key'
export TELEGRAM_BOT_TOKEN='your-telegram-bot-token'
export TELEGRAM_CHAT_ID='your-telegram-chat-id'
export HOME_ADDRESS='서울시 강남구 테헤란로 123'
python main.py
```

정상 실행 시 `settings.yaml` 로드와 기본 부트스트랩 상태를 출력합니다.

## Railway

- `Procfile` 기준 실행 명령: `worker: python main.py`
- cron 스케줄은 Railway 대시보드에서 설정합니다.
- MVP 기준 권장 스케줄: 매 시간 정각 `0 * * * *`
