# T-007-report — 알림 스케줄링 재설계 + 배포

**완료일**: 2026-04-19  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `core/scheduler.py` 구현 — 당일 일정 분석 후 알림 계획 목록 반환 | ✅ | 계획 생성, 캐시 재사용, due alert 추출 포함 |
| 알림 종류: `준비 시작` / `출발` | ✅ | `ScheduledAlert.alert_type`로 구분 |
| 출발 알림 시각 = 일정 시작 - 이동 시간 - `buffer_minutes` | ✅ | T-004 계산 결과 재사용 |
| 준비 알림 시각 = 출발 알림 시각 - `prep_minutes` | ✅ | `prep_minutes=0`이면 생략 가능 구조 |
| 현재 시각이 각 알림 시각의 ±`alert_window_minutes` 이내이면 전송 | ✅ | `get_due_alerts()`에서 처리 |
| 알림 계획을 `.runtime/schedule_today.json`에 저장 | ✅ | 날짜 불일치 시 재계산 |
| 준비 알림 메시지 포맷 반영 | ✅ | 준비 시작/출발 예정/경로 요약 포함 |
| 출발 알림 메시지 포맷 반영 | ✅ | 장소/이동 수단/소요 시간/출발 시각/경로 요약 포함 |
| 이동 시간이 추정값이면 `(이동 시간 추정)` 표기 | ✅ | prep/departure 메시지 모두 반영 |
| Oracle crontab 가이드 작성 | ✅ | `deploy/oracle_crontab.md` 추가 |
| GitHub Actions 30분 cron 워크플로우 작성 | ✅ | `.github/workflows/departure_check.yml` 추가 |
| 두 방식 모두 동일한 `main.py`를 진입점으로 사용 | ✅ | 배포별 코드 분기 없음 |
| `README.md`에 두 배포 방식 선택 가이드 추가 | ✅ | Oracle/GHA 가이드 포함 |

---

## 원래 기획과 달라진 점

- 기존 이벤트 단위 dedup은 prep/departure 두 단계 알림을 막아버리므로, alert 단위 dedup key로 확장함

---

## 발생한 에러/이슈

- 없음

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: `schedule_today.json`은 당일 날짜 기준 캐시이므로, 날짜가 바뀌면 반드시 재생성되어야 함
- 주의할 것: 파이프라인 완료는 코드 완료만으로 끝나지 않고 Oracle 또는 GitHub Actions에서 실제 알림 수신 확인이 필요함
- 제거 예정: 없음
