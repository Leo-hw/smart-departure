# PIPELINE.md — 태스크 큐

> Codex가 이 파일을 읽고 파이프라인을 자율 실행합니다.
> Claude(PM)가 큐를 관리합니다.

---

## 현재 활성 파이프라인: Phase 2

| 순서 | 티켓 | 상태 | 설명 |
|------|------|------|------|
| 1 | T-001 | 🟢 DONE | 프로젝트 기반 세팅 |
| 2 | T-002 | 🟢 DONE | Google Calendar 연동 |
| 3 | T-003 | 🟢 DONE | Google Maps 대중교통 이동 시간 |
| 4 | T-004 | 🟢 DONE | 출발 시각 계산 + 알림 판단 엔진 |
| 5 | T-005 | 🟢 DONE | 알림 채널 라우팅 + 전송 |
| 6 | T-006 | 🟢 DONE | 중복 알림 방지 (dedup) |
| 7 | T-007 | 🟢 DONE | 알림 스케줄링 재설계 + 배포 (Oracle/GHA) |
| 8 | T-008 | 🟢 DONE | 카카오 Maps 자동차 길찾기 |
| 9 | T-010 | 🟢 DONE | 견고성 + 놓친 알림 catch-up |
| 10 | T-009 | 🟡 READY | occasion별 준비 단계 알림 |

**파이프라인 완료 기준**: T-008 + T-010 + T-009 완료

> ⚠️ T-010은 운영 중 발견된 크래시(SSL 타임아웃)·알림 유실 대응. 우선순위 높음.
>
> **병렬 실행 규칙**: T-008 ∥ T-010 동시 진행 가능 (파일 겹침 없음).
> T-009는 T-010과 `scheduler.py`·`settings.yaml`을 함께 고치고, catch-up "준비단계 가장 최근만" 로직이
> T-009의 다단계 prep 위에서 동작해야 하므로 **T-010 머지 후** 진행. 동시 실행 금지.

---

## 대시보드 Queue

<!-- QUEUE:START -->
| ID | 제목 | 담당 | 상태 | 의존 |
|----|------|------|------|------|
| T-001 | 프로젝트 기반 세팅 | Codex | DONE | - |
| T-002 | Google Calendar 연동 | Codex | DONE | T-001 |
| T-003 | Google Maps 대중교통 이동 시간 | Codex | DONE | T-001 |
| T-004 | 출발 시각 계산 + 알림 판단 엔진 | Codex | DONE | T-002, T-003 |
| T-005 | 알림 채널 라우팅 + 전송 | Codex | DONE | T-004 |
| T-006 | 중복 알림 방지 (dedup) | Codex | DONE | T-005 |
| T-007 | 알림 스케줄링 재설계 + 배포 | Codex | DONE | T-006 |
| T-008 | 카카오 Maps 자동차 길찾기 | Codex | DONE | T-007 |
| T-010 | 견고성 + 놓친 알림 catch-up | Codex | DONE | T-007 |
| T-009 | occasion별 준비 단계 알림 | Codex | READY | T-010 |
<!-- QUEUE:END -->

---

## 자율 실행 규칙

### 티켓 N 시작 전
1. `current-task.md` → `tickets/T-00N.md` 심링크 업데이트
2. `git status`로 레포 확인
3. `git checkout -b feature-T-00N-설명`

### 파이프라인 중단 조건
- AC ❌ 항목 존재
- 환경변수 누락으로 테스트 불가
- Maps API 응답 구조 예상과 다름

중단 시 `PIPELINE_BLOCKED.md`에 사유 기록 후 Claude(PM)에게 알림.
