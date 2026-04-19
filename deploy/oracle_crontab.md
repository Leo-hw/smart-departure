# Oracle Crontab Deployment

Oracle VM에서 `main.py`를 30분 간격으로 실행하는 기준 가이드입니다.

## 1. 앱 배치

```bash
git clone <repository-url> ~/smart-departure
cd ~/smart-departure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 환경변수 준비

`.env` 파일 또는 셸 환경변수에 아래 값을 넣습니다.

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_CALENDAR_IDS`
- `GOOGLE_MAPS_API_KEY`
- `HOME_ADDRESS`
- `DISCORD_WEBHOOK_URL`
- Telegram도 함께 쓰면 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## 3. Crontab 등록

```cron
*/30 * * * * cd /home/ubuntu/smart-departure && /home/ubuntu/smart-departure/.venv/bin/python main.py >> /var/log/smart-departure.log 2>&1
```

## 4. 확인 포인트

- `.runtime/schedule_today.json`이 생성되는지 확인
- `.runtime/sent_alerts.json`이 성공 전송 후 기록되는지 확인
- `/var/log/smart-departure.log`에 `delivery failed`가 없는지 확인
