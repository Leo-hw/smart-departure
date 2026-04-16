# smart-departure

Google Calendar 일정과 지도 API를 기반으로 출발 시각을 계산해 Discord webhook, Telegram 또는 둘 다로 알림을 보내는 Railway cron worker입니다.

## Requirements

- Python 3.11+
- 필수 환경변수
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_CALENDAR_IDS`
  - `GOOGLE_MAPS_API_KEY`
  - `HOME_ADDRESS`
- 채널별 환경변수
  - Discord 사용 시: `DISCORD_WEBHOOK_URL`
  - Telegram 사용 시: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Notification Channels

`shared/config/settings.yaml`의 `notification.enabled_channels`로 활성 채널을 선택합니다.

```yaml
notification:
  enabled_channels:
    - discord
    - telegram
```

- `discord`만 넣으면 Discord webhook만 사용합니다.
- `telegram`만 넣으면 Telegram만 사용합니다.
- 둘 다 넣으면 두 채널 모두 전송합니다.

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
export DISCORD_WEBHOOK_URL='your-discord-webhook-url'
export HOME_ADDRESS='서울시 강남구 테헤란로 123'
python3 main.py
```

Telegram도 함께 쓰려면 아래를 추가합니다.

```bash
export TELEGRAM_BOT_TOKEN='your-telegram-bot-token'
export TELEGRAM_CHAT_ID='your-telegram-chat-id'
```

정상 실행 시 `settings.yaml`을 로드하고, 현재 알림 대상 일정 수와 채널 전송 시도 수를 출력합니다.

## Railway

- `Procfile` 기준 실행 명령: `worker: python main.py`
- cron 스케줄은 Railway 대시보드에서 설정합니다.
- MVP 기준 권장 스케줄: 매 시간 정각 `0 * * * *`
