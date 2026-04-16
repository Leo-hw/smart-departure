# PIPELINE.md — 태스크 큐

> Codex가 이 파일을 읽고 파이프라인을 자율 실행합니다.
> Claude(PM)가 큐를 관리합니다.

---

## 현재 활성 파이프라인: Phase 1 (MVP)

| 순서 | 티켓 | 상태 | 설명 |
|------|------|------|------|
| 1 | T-001 | 🟢 DONE | 프로젝트 기반 세팅 |
| 2 | T-002 | 🟢 DONE | Google Calendar 연동 |
| 3 | T-003 | 🟢 DONE | Google Maps 대중교통 이동 시간 |
| 4 | T-004 | 🟢 DONE | 출발 시각 계산 + 알림 판단 엔진 |
| 5 | T-005 | 🟡 READY | 텔레그램 알림 전송 |
| 6 | T-006 | ⬜ BACKLOG | 중복 알림 방지 (dedup) |

**파이프라인 완료 기준**: T-006 완료 + Railway 실제 알림 수신 확인

---

## 대시보드 Queue

<!-- QUEUE:START -->
| ID | 제목 | 담당 | 상태 | 의존 |
|----|------|------|------|------|
| T-001 | 프로젝트 기반 세팅 | Codex | DONE | - |
| T-002 | Google Calendar 연동 | Codex | DONE | T-001 |
| T-003 | Google Maps 대중교통 이동 시간 | Codex | DONE | T-001 |
| T-004 | 출발 시각 계산 + 알림 판단 엔진 | Codex | DONE | T-002, T-003 |
| T-005 | 텔레그램 알림 전송 | Codex | READY | T-004 |
| T-006 | 중복 알림 방지 (dedup) | Codex | BACKLOG | T-005 |
| T-007 | 카카오 Maps 자동차 길찾기 | Codex | BACKLOG | T-006 |
| T-008 | settings.yaml 이동 수단 설정 + 캘린더 오버라이드 | Codex | BACKLOG | T-007 |
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
