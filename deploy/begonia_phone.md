# 인계: begonia 폰에서 smart-departure 운영 (and-to-server → smart-departure 세션)

> 2026-11-14 후속: T-017에서 알림 키를 안정화했고 Actions 자동 `schedule`을 제거했다. 폰에서 변경 코드의 실제 알림 재발송 여부는 아직 검증하지 않았다. 세부 내용은 `tickets/T-017-report.md` 참고.

> 작성 2026-11-14, and-to-server 세션. 원 지시서: ai-dashboard `docs/handoff-and-to-server-smart-departure.md`.
> 이 문서는 **봇이 지금 어디서 어떻게 도는지**와 **남은 문제**를 smart-departure 세션이 이어받기 위한 것이다.
> 서버(폰) 자체 문제는 and-to-server 저장소(`docs/device-notes.md`)가 담당.

## 1. 현재 운영 방식

| 항목 | 값 |
|---|---|
| 기기 | begonia (Redmi Note 8 Pro, Ubuntu Touch 24.04), 충전기 상시 연결 |
| 실행 | systemd **사용자** 타이머 `smart-departure.timer` → `smart-departure.service` (oneshot) |
| 주기 | `OnCalendar=*:0/5` (5분, 정각 기준), `Persistent=true`, `AccuracySec=30s` |
| 코드 위치 | 폰 `~/apps/smart-departure` (이 저장소 클론, `main` 추적) |
| 코드 갱신 | 실행마다 `ExecStartPre=-git pull -q --ff-only` → **main에 머지하면 다음 5분 실행부터 반영** (pull 실패해도 실행은 계속) |
| 파이썬 | 3.12.3, `.venv` (requirements.txt 설치) |
| 시간대 | 서비스 `Environment=TZ=Asia/Seoul` |
| 비밀값 | 폰 `~/apps/smart-departure/.env` (600, git 제외). 회장이 직접 넣음. 에이전트는 값을 읽거나 출력하지 않음 |
| 상태 파일 | `.runtime/sent_alerts.json`(중복 방지), `.runtime/travel_cache.json` |
| 서비스 파일 원본 | and-to-server `ut/systemd/smart-departure.{service,timer}` |

GitHub Actions 워크플로·cron-job.org 외부 트리거는 쓰지 않는다(T-012·T-014 대체).

### 자주 쓰는 명령 (폰에서, sudo 불필요)

```sh
systemctl --user list-timers smart-departure.timer          # 다음/직전 실행
journalctl --user -u smart-departure -n 30 --no-pager       # 최근 로그
journalctl --user -u smart-departure --since today | grep -E "plan event|due|attempted|Failed"
systemctl --user start smart-departure.service              # 지금 1회 실행
systemctl --user stop smart-departure.timer                 # 일시 중지 (disable 하면 재부팅 후에도 꺼짐)
cat ~/apps/smart-departure/.runtime/sent_alerts.json        # 보낸 알림 기록
```

## 2. 검증 결과 (인계서 5절 완료 기준)

| 기준 | 결과 |
|---|---|
| 5분 간격 실행, 모두 성공 | 2026-11-13 17:55–21:10 **40회 / 실패 0**, 간격 정확히 300초. 1회 4–5초(`git pull` 포함) |
| 재부팅 후 자동 재개 | 2026-11-14 12:26 부팅 → 12:30 실행 정상. 다른 서비스도 전부 자동 시작 |
| 시험 일정 알림 ±5분 | 13:30 서울역 일정(12:31 등록). **출발 알림 12:40:28** — 계산된 출발 12:42보다 2분 일찍, 통과 |
| 알림 **한 번만** | **불통과** — 준비 알림이 2번 옴 (아래 문제 1) |
| 지도 | Google Routes API 실제 값(`estimated=False`). 24 → 38 → 25분 (5분 간격) |

시험 일정 로그 (요약):

```
12:35 plan travel=24m departure=12:56 prep=11:56 → due prep(catch_up)      → 준비 알림 1
12:40 plan travel=38m departure=12:42 prep=11:42 → due prep(catch_up)      → 준비 알림 2 (중복)
                                                 → due departure(on_time) → 출발 알림
12:45 plan travel=25m departure=12:55 prep=11:55 → 준비 알림 3 + 출발 알림 2 (둘 다 중복)
12:50 travel=32m → 출발 알림 3
12:55 travel=24m → 준비·출발 알림 시도 2 (준비 11:56은 12:35에 보낸 것과 같은 시각인데 다시 시도됨 — 원인 미확인)
13:00 travel=32m, 13:05 travel=25m → 시도 0 (출발 시각이 지나 알림 창 밖)
```

→ 일정 하나에 `Notifications attempted` 합계 **8건**(12:35–12:55). 이동 시간이 바뀔 때마다 다시 나간다.
→ 12:55의 준비 알림 재시도는 같은 키가 이미 기록돼 있었는데도 일어났다. dedup 기록이 덮어써지거나 TTL 판정이 알림 시각 기준인지 함께 확인할 것.

## 3. 남은 문제 (우선순위 순, 모두 코드 미수정 — 이 저장소의 일)

### 문제 1. 이동 시간이 바뀌면 같은 알림이 다시 나간다 (중복) — **수정 권장**

- 원인: `core/scheduler.py` `ScheduledAlert.dedup_key` = `f"{event_id}:{alert_type}:{alert_time.isoformat()}"`.
  이동 시간이 바뀌면 `alert_time`이 바뀌어 다른 키가 되고, `dedup.py`가 새 알림으로 본다.
- 영향: 준비·출발 알림 모두 이동 시간이 바뀔 때마다 다시 나간다(시험에서 12:45에 실제로 둘 다 재발송). 대중교통은 5분 사이에도 크게 바뀐다(문제 2).
- 제안: 키에서 `alert_time`을 빼고 `event_id:alert_type`(일정 시작 시각이 바뀐 경우를 위해 `event_start` 포함 가능)로.
  T-009(준비 단계별 알림)를 하면 단계 이름을 키에 넣는다. 테스트: 같은 일정을 이동 시간만 바꿔 두 번 평가 → 두 번째는 dedup skip.
- 기존 `.runtime/sent_alerts.json` 키 형식이 바뀌므로 배포 직후 1회 중복 가능(TTL 60분이라 자연 정리).

### 문제 2. 대중교통 소요 시간이 실행마다 크게 흔들린다

- 같은 경로가 12:35 24분 → 12:40 38분 → 12:45 25분. Routes 요청에 `departureTime`이 없어 "지금 출발" 기준으로 계산되고,
  대중교통은 다음 차 시간에 따라 값이 달라지는 것으로 보인다(추정, 미검증).
- 제안(택1): 출발 예정 시각을 `departureTime`으로 넘기기 / 일정별로 처음 계산값을 고정 / 늘어나는 쪽만 반영.
  문제 1을 고치면 중복은 사라지지만 출발 시각이 실행마다 바뀌는 건 남는다.

### 문제 3. 캘린더 하나가 접근 불가면 전체 실행이 실패한다

- `GOOGLE_CALENDAR_IDS` 중 하나라도 404면 `startup failed: HttpError`로 exit 1 → 나머지 캘린더 알림도 안 나감.
  2026-11-13에 5번째 캘린더(서비스 계정 미공유)로 실제 발생 → 회장이 그 ID를 `.env`에서 뺌(현재 4개).
- 제안: `core/calendar_service.py` 루프에서 캘린더별 `HttpError`를 잡아 경고 로그 후 건너뛰기.

### 문제 4. (결정 대기) 대중교통을 카카오맵으로 바꿀지 — T-016 후보

- 평가 내용은 `tickets/T-015.md` "추가 평가" 절. 시간 차이 1–3분, 키 하나로 운영 가능. 카카오는 출발 시각 지정 파라미터가 없음(문제 2 해결책과 맞물림).

### 참고: 캘린더 동기화 지연

- 시험 때 폰 캘린더 앱에서 만든 일정이 Google에 늦게 올라가 첫 확인에서 안 보였다(앱에서 새로고침 후 반영). 봇 문제 아님.

## 4. smart-departure 세션이 할 일 (원 지시서 7절 + 위 문제)

- [ ] `PIPELINE.md`: T-012·T-014는 폰 이전으로 대체 → 정리, `PIPELINE_BLOCKED.md` 닫기
- [ ] T-009(준비 단계 알림) 차단 해제 — 문제 1 수정과 함께 하는 게 자연스러움
- [ ] 문제 1 티켓화·수정 (권장 우선)
- [ ] 문제 2·3 티켓화
- [ ] T-016(카카오) 여부 결정
- [ ] `deploy/oracle_crontab.md`·`external_trigger_setup.md`는 쓰지 않은 안으로 표시하거나 정리

## 5. 운영 중 문제가 생기면

| 증상 | 먼저 볼 것 | 담당 |
|---|---|---|
| 알림이 안 옴 | `journalctl --user -u smart-departure -n 50` — `Failed`/`startup failed` 여부, `Today's plans` 수 | 로그에 예외 → 이 저장소 / 타이머 안 돎 → and-to-server |
| `Today's plans: 0`인데 일정 있음 | 일정에 **장소**가 있는지(없으면 건너뜀), 3시간(`lookahead_hours`) 안인지, 봇이 보는 캘린더인지, 캘린더 앱 동기화 | 회장 / 이 저장소 |
| `estimated=True` | 지도 API 실패 → 캐시나 30분 추정값 사용 중. 키·쿼터·결제 확인 | 회장(키) / 이 저장소 |
| 같은 알림이 여러 번 | 문제 1 | 이 저장소 |
| 코드 바꿨는데 반영 안 됨 | 폰 `git -C ~/apps/smart-departure log -1`, pull 실패(로컬 수정 등) 여부 | and-to-server |
| `.env` 값 변경 | 회장이 직접 수정. 다음 실행부터 반영(재시작 불필요) | 회장 |

폰 접속·서비스 파일 수정·재부팅은 and-to-server 세션에 요청한다. 이 저장소 세션은 코드만 고치고 main에 머지하면 된다.
