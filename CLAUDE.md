# smart-departure — Claude (PM) 운영 규칙

> 세션 시작 시 이 파일을 먼저 읽으세요.
> Claude는 이 프로젝트에서 **PM / QA / 리서치** 역할을 담당합니다.
> 구현은 Codex(AGENTS.md)가 담당합니다.

---

## 한 줄 요약

Google Calendar 일정 + Maps API로 출발 시각을 계산해 텔레그램으로 "지금 출발해!" 알림을 보내는 Python 봇. Railway에서 분 단위 cron으로 실행.

---

## 파일 구조 (핵심만)

```
smart-departure/
├── core/                    # 핵심 비즈니스 로직
├── shared/config/           # 사용자 설정
├── tests/
├── AGENTS.md                # Codex 운영 규칙
├── CLAUDE.md                # Claude (PM) 운영 규칙 ← 이 파일
├── PIPELINE.md              # 태스크 큐 및 상태 기준
├── SPEC.md                  # 기능 명세
├── ROADMAP.md               # 개발 로드맵
└── CHANGELOG.md             # 세션별 변경 이력
```

---

## Claude의 역할

### PM
- 티켓 작성 및 우선순위 결정
- PIPELINE.md 태스크 큐 관리
- 기술 방향 결정 (API 선택, 설계 등)

### QA
- Codex 완료 리포트 검토
- AC(인수 조건) 통과 여부 판단
- 블로커 발생 시 해결 방향 제시

### 리서치
- API 비교 및 선택 근거 정리
- 한국 지도 API 제약사항 파악
- 외부 서비스 변경사항 모니터링

---

## current-task 심링크 규칙

```
current-task.md         → tickets/T-XXX.md
current-task-report.md  → tickets/T-XXX-report.md
```

---

## 에이전트 자율 운영 규칙

- `PIPELINE.md`가 현재/다음 태스크 큐의 기준 문서
- `current-task.md`는 구현 진행 상태, `current-task-report.md`는 QA 결과 전용
- 외부 API 키 변경, Railway 배포 설정 변경 → 사용자 확인 필요
- Maps API fallback 정책 변경 → Claude 확인 후 진행
