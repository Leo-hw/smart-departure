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
| 10 | T-011 | 🟢 DONE | [핫픽스] 당일 추가 일정 미반영 (스냅샷 staleness) |
| 11 | T-012 | 🟠 VERIFY | GHA 실행 신뢰성 (빈도↑ + catch-up 보강) |
| 12 | T-013 | 🟠 VERIFY | public 안전화: 로그/캐시 민감정보 제거 |
| 13 | T-014 | 🟠 VERIFY | 외부 트리거 (cron-job.org → workflow_dispatch) |
| 14 | T-009 | 🚧 BLOCKED:T-014 | occasion별 준비 단계 알림 |

**파이프라인 완료 기준**: T-014 + T-009 완료

> 🔥 T-014 핵심: GHA `schedule:` cron이 1.5~4.7시간 지연 → 외부 cron이 workflow_dispatch(즉시 실행)를
> 매 5분 호출해 정시성 확보. 라이브 측정상 dispatch는 2초 내 실행됨. 셋업 가이드: deploy/external_trigger_setup.md
>
> T-012/T-013은 코드·마스킹 검증 끝, 정시성은 T-014가 마무리. T-009는 그 위에 얹는다.

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
| T-011 | [핫픽스] 당일 추가 일정 미반영 (스냅샷 staleness) | Codex | DONE | T-010 |
| T-012 | GHA 실행 신뢰성 (빈도↑ + catch-up 보강) | Codex | VERIFY | T-010, T-011 |
| T-013 | public 안전화: 로그/캐시 민감정보 제거 | Codex | VERIFY | T-012 |
| T-014 | 외부 트리거 (cron-job.org → workflow_dispatch) | Codex+사용자 | VERIFY | T-012, T-013 |
| T-009 | occasion별 준비 단계 알림 | Codex | BLOCKED:T-014 | T-014 |
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
