# smart-departure — Codex 운영 규칙

> Codex는 이 프로젝트에서 **구현** 역할을 담당합니다.
> 세션 시작 시 이 파일과 PIPELINE.md를 먼저 읽으세요.

---

## 1. current-task 심링크 규칙

**작업 시작 시**:
```bash
ln -sf tickets/T-XXX.md ./current-task.md
```

**작업 완료 시**:
```bash
ln -sf tickets/T-XXX-report.md ./current-task-report.md
```

---

## 2. PIPELINE.md가 존재하면 파이프라인 모드로 실행

```
[티켓 N 시작]
  → current-task.md 심링크 업데이트
  → 브랜치 생성 (feature-T-00N-설명)
  → 구현

[티켓 N 완료]
  → 자가 QA 체크리스트 실행
  → 리포트 작성 (tickets/T-00N-report.md)
  → 심링크 업데이트
  → CHANGELOG.md 갱신
  → Git 커밋
  → 자가 QA 전부 통과 시 → 다음 티켓
  → 자가 QA 실패 시 → PIPELINE_BLOCKED.md 작성 후 중단
```

---

## 3. 작업 완료 후 자동으로 해야 할 것

### Step 1 — 티켓 상태 업데이트
`tickets/T-XXX.md` 상단 상태를 `🟢 DONE`으로 변경, AC 체크박스 `[x]`로 표시

### Step 2 — 리포트 작성
`tickets/T-XXX-report.md` 작성. 포함 내용:
- AC 결과 (✅ / ❌ / ⚠️)
- 원래 기획과 달라진 점
- 발생한 에러/이슈
- 다음 작업자에게 전달할 주의사항

### Step 3 — 심링크 업데이트

### Step 4 — CHANGELOG.md 기록

### Step 5 — Git 커밋
```bash
git checkout -b feature-T-XXX-설명
git add [변경된 소스 파일]
git commit -m "feat(T-XXX): 구현 내용 요약"
git add tickets/ CHANGELOG.md current-task.md current-task-report.md
git commit -m "docs(T-XXX): 리포트 및 상태 업데이트"
git checkout main
git merge feature-T-XXX-... --no-ff -m "merge(T-XXX): 작업명 완료"
```

> ⚠️ 브랜치명 슬래시(`/`) 사용 금지 — `feature-T-XXX-설명` 형태 사용

---

## 4. 자가 QA 체크리스트

- [ ] 모든 AC가 ✅인가? ❌ 또는 ⚠️ 항목이 있으면 PIPELINE_BLOCKED.md 작성
- [ ] `python -m py_compile` 문법 오류 없음
- [ ] 환경변수 하드코딩 없음 (모두 os.environ 참조)
- [ ] Maps API fallback 동작 확인
- [ ] 중복 알림 방지 로직 영향 없음

---

## 5. 코드 규칙

### 환경변수
모든 민감 정보는 `os.environ.get()`으로만 참조. 하드코딩 금지.

### Maps API 추상화
`maps_service.py`는 transport 타입에 따라 내부적으로 provider를 선택하는 구조 유지:
```python
def get_travel_time(origin, destination, transport_mode) -> int:  # minutes
    provider = _select_provider(transport_mode)
    return provider.calculate(origin, destination)
```

### 커밋 메시지 컨벤션
| 접두사 | 사용 시점 |
|--------|-----------|
| `feat(T-XXX):` | 기능 구현 |
| `fix(T-XXX):` | 버그 수정 |
| `docs(T-XXX):` | 티켓/리포트/문서 |
| `refactor(T-XXX):` | 동작 변경 없는 정리 |

### dedup 파일 경로
`.runtime/sent_alerts.json` — git ignore 대상
