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
| 12 | T-013 | 🔥 READY | public 안전화: 로그/캐시 민감정보 제거 |
| 13 | T-009 | 🚧 BLOCKED:T-013 | occasion별 준비 단계 알림 |

**파이프라인 완료 기준**: T-012 + T-013 + T-009 완료

> 🔥 T-013 긴급: public repo에서 일정명/장소가 Actions 로그·캐시로 노출 중. 마스킹 + 과거분 purge 필요.
> 작업 중에는 임시 private 또는 워크플로우 비활성화로 누출 차단, 완료 후 재공개.
>
> **순서 규칙**: T-013(마스킹) → T-012 D검증 마무리(안전한 public 실행) → T-009.
> T-012·T-013·T-009 모두 scheduler/main/dedup/settings를 건드리므로 순차 진행, 동시 금지.

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
| T-013 | public 안전화: 로그/캐시 민감정보 제거 | Codex | READY | T-012 |
| T-009 | occasion별 준비 단계 알림 | Codex | BLOCKED:T-013 | T-013 |
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
