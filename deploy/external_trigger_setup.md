# 외부 트리거 셋업 가이드 (cron-job.org → GHA workflow_dispatch)

> 목적: GHA `schedule:` cron의 지연/누락(실측 1.5~4.7시간)을 우회.
> 신뢰성 있는 외부 cron이 매 5분 `workflow_dispatch`를 호출 → GHA가 2초 내 즉시 실행.
> 새 서버 불필요. 무료.

---

## 동작 원리

```
cron-job.org (무료, 정시 보장)
   ── 매 5분 HTTP POST ──▶  GitHub API: workflow_dispatch
                                  │ (즉시, 몇 초 내)
                                  ▼
                           GHA가 main.py 실행 → 알림 판단/전송
```

`schedule:`(저우선순위, 막힘)이 아니라 `workflow_dispatch`(push/버튼과 동급, 즉시)를 쓰는 게 핵심.

---

## 1단계 — fine-grained PAT 발급

GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**

| 항목 | 값 |
|---|---|
| Token name | `smart-departure-trigger` |
| Resource owner | `Leo-hw` |
| Expiration | 원하는 기간 (예: 90일 또는 1년) — 만료 시 재발급 |
| Repository access | **Only select repositories** → `smart-departure` |
| Permissions → Repository permissions → **Actions** | **Read and write** |

> `Metadata: Read-only`는 자동 포함됨. 다른 권한은 줄 필요 없음.
> **Generate token** 누르고 나온 `github_pat_...` 값을 복사해 둠 (한 번만 보임).

⚠️ 이 PAT는 cron-job.org에만 넣고, 코드/repo에 절대 커밋하지 말 것.

---

## 2단계 — cron-job.org 잡 생성

1. https://cron-job.org 가입 (무료)
2. **Create cronjob**
3. 설정:

| 항목 | 값 |
|---|---|
| Title | `smart-departure trigger` |
| URL | `https://api.github.com/repos/Leo-hw/smart-departure/actions/workflows/departure_check.yml/dispatches` |
| Schedule | Every 5 minutes (`*/5`) |
| Request method | **POST** |

4. **Advanced → Headers** 에 추가:

```
Accept: application/vnd.github+json
Authorization: Bearer github_pat_여기에_PAT
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
User-Agent: smart-departure-cron
```

> GitHub API는 `User-Agent` 헤더가 없으면 403을 줌 — 반드시 포함.

5. **Request body** (POST 바디):

```json
{"ref":"main"}
```

6. **Save**.

---

## 3단계 — 동작 확인

### 즉시 확인 (cron-job.org)
- cron-job.org 잡 상세 → 마지막 실행 결과가 **HTTP 204 No Content** 면 성공 (dispatch는 204를 반환함).
- 403 → 헤더(특히 User-Agent / Authorization) 확인
- 404 → URL의 owner/repo/워크플로우 파일명 확인, PAT의 repo 접근 범위 확인

### GHA 쪽 확인
```bash
gh run list -R Leo-hw/smart-departure --limit 10 \
  --json event,createdAt,status -q '.[] | "\(.event)  \(.createdAt)  \(.status)"'
```
- `event=workflow_dispatch` run이 **~5분 간격**으로 들어오면 성공.

---

## 4단계 — 실제 알림 검증

1. 캘린더에 **2~3시간 뒤** 일정 추가 (장소 필드 입력 필수)
2. 다음 dispatch 실행부터 plan에 잡힘
3. 준비/출발 시각에 Discord 알림이 **목표 ±5분**으로 도착하는지 확인
4. (public이면) Actions 로그에 일정명 없는지 확인 (T-013 마스킹)

---

## 운영 메모

- **백업 레이어**: 워크플로우의 `schedule:` cron은 그대로 둠. cron-job.org가 죽어도 (부정확하게나마) 받쳐줌.
- 현재 GitHub `schedule:`은 노이즈를 줄이기 위해 매시간 백업(`0 * * * *`)으로만 둠.
- **비용**: public repo라 GHA 무제한 무료. cron-job.org 무료. PAT 무료.
- **rate limit**: 인증 API 5000/시간. 5분당 1회(=12/시간)라 여유.
- **PAT 만료**: 만료되면 dispatch가 401로 실패 → cron-job.org 잡이 실패로 뜸. 재발급 후 헤더 교체.
- **보안**: PAT 유출 시 최악은 "워크플로우 실행/취소"뿐. 즉시 GitHub에서 해당 PAT revoke 후 재발급.
