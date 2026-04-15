# T-001-report — 프로젝트 기반 세팅

**완료일**: 2026-04-15  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `main.py` 실행 시 환경변수 누락 여부를 체크하고 명확한 에러 메시지 출력 | ✅ | 누락 변수명을 한 번에 출력하도록 구현 |
| `shared/config/settings.yaml` 로드 성공 | ✅ | `HOME_ADDRESS` 환경변수 오버라이드 포함 |
| `requirements.txt` 작성 완료 | ✅ | `google-auth`, `google-api-python-client`, `requests`, `pyyaml` 반영 |
| `.gitignore`에 `.env`, `.runtime/`, `*.pyc`, `.venv/` 포함 | ✅ | `__pycache__/`도 함께 제외 |
| `README.md`에 로컬 실행 방법 작성 | ✅ | 가상환경, 환경변수, 실행 예시 포함 |
| Railway용 `Procfile` 또는 `railway.toml` 작성 | ✅ | `worker: python main.py` 추가 |

---

## 원래 기획과 달라진 점

- 로컬 Python에 `pyyaml`가 없어도 현재 `settings.yaml` 구조는 읽을 수 있도록 최소 YAML fallback 파서를 추가함

---

## 발생한 에러/이슈

- 기본 셸에서 `python` 명령이 없어서 검증은 `python3`로 수행함

---

## 다음 작업자에게 전달할 주의사항

- 유지할 것: `HOME_ADDRESS`는 항상 환경변수 값이 `settings.yaml`보다 우선해야 함
- 주의할 것: `core/maps_service.py`의 provider 선택 인터페이스는 AGENTS.md 규칙대로 유지해야 함
- 제거 예정: YAML fallback 파서는 `pyyaml` 설치가 항상 보장되는 배포 환경에서는 필수는 아니지만, 로컬 부트스트랩 안정성 때문에 남겨둠
