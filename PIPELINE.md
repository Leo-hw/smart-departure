# PIPELINE.md — 태스크 큐

> Codex가 이 파일을 읽고 파이프라인을 자율 실행합니다.
> Claude(PM)가 큐를 관리합니다.

---

## 현재 활성 파이프라인: begonia 폰 운영

> 운영 실행은 [begonia 폰 타이머](./deploy/begonia_phone.md)가 담당한다. Actions 자동 실행은 중지하고 수동 실행만 남겼다. T-012·T-014의 미검증 GHA AC는 완료로 간주하지 않는다.

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
| 11 | T-012 | ⚪ SUPERSEDED | GHA 실행 빈도 검증을 폰 타이머로 대체; catch-up 코드는 유지 |
| 12 | T-013 | 🟢 DONE | public 안전화: 로그/캐시 민감정보 제거 |
| 13 | T-014 | ⚪ SUPERSEDED | 외부 트리거 대신 폰 타이머 운영 |
| 14 | T-015 | 🟢 DONE | Google 이동 시간 Routes API 전환·폰 실키 확인 |
| 15 | T-017 | 🟢 DONE | 이동 시간 변동 시 중복 알림 방지 |
| 16 | T-009 | 🟢 DONE | occasion별 준비 단계 알림 |
| 17 | T-018 | 🟢 DONE | 대중교통 이동 시간 변동 정책 |
| 18 | T-019 | 🟢 DONE | 캘린더 일부 실패 시 나머지 일정 처리 |
| 19 | T-020 | 🟢 DONE | 제공자 중립 Google 대중교통 경로 안내 |

**현재 후속 작업**: T-016 카카오 대중교통 전환 여부는 별도 결정.

> T-016(카카오 대중교통 전환)은 보류한다. 현재 Google Routes가 폰에서 실제 값을 반환하며, 카카오 전환은 출발 시각 변동 문제를 해결하지 않는다. T-018 결과를 보고 재평가한다. 전환한다면 소요 시간 계산에 선택한 동일 경로의 승하차·환승·도보 단계를 알림에 간단히 표시하고 카카오맵 길찾기 링크를 제공한다.

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
| T-012 | GHA 실행 신뢰성 (빈도↑ + catch-up 보강) | Codex | SUPERSEDED | T-010, T-011 |
| T-013 | public 안전화: 로그/캐시 민감정보 제거 | Codex | DONE | T-012 |
| T-014 | 외부 트리거 (cron-job.org → workflow_dispatch) | Codex+사용자 | SUPERSEDED | T-012, T-013 |
| T-015 | Google 이동 시간 Routes API 전환 | and-to-server | DONE | - |
| T-017 | 이동 시간 변동 시 중복 알림 방지 | Codex | DONE | T-015 |
| T-009 | occasion별 준비 단계 알림 | Codex | DONE | T-017 |
| T-018 | 대중교통 이동 시간 변동 정책 | Codex | DONE | T-017 |
| T-019 | 캘린더 일부 실패 시 나머지 일정 처리 | Codex | DONE | - |
| T-020 | 제공자 중립 Google 대중교통 경로 안내 | Codex | DONE | T-018, T-019 |
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
