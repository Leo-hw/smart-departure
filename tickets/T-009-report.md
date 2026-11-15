# T-009 리포트 — occasion별 준비 단계 알림

## AC 결과

- ✅ 다섯 `prep_profiles`를 설정하고 제목 키워드 우선순위와 `occasion:` 설명 오버라이드를 구현했다.
- ✅ 준비 단계는 출발 시각에서 각 오프셋을 빼 계산한다. `0`분 출발 단계는 기존 출발 알림 경로 하나만 사용한다.
- ✅ 단계 라벨을 안정적인 `stage_id`로 사용해 T-017 dedup 키(`event_id:event_start:prep:stage_id`)로 각각 구분한다. 이동 시간 변동은 키에 영향을 주지 않는다.
- ✅ `schedule_today.json`에 occasion과 단계별 시각·실제 alert key를 저장하고, 스냅샷 버전 2로 이전 형식의 재사용을 막았다.
- ✅ 단일 `schedule.prep_minutes` 설정을 제거했다.
- ✅ 59개 단위 테스트, `py_compile`, `git diff --check`를 통과했다. Maps fallback 및 dedup 기존 테스트도 통과했다.

## 기획 대비 변경

- 예시의 `event_id_stage_label` 대신 T-017의 일정 시작 시각을 포함한 안정 dedup 키를 사용했다.
- 테스트 및 이전 호출부 호환을 위해 `SchedulePlan.prep_alert_time` 필드는 남겼지만 실제 계획 생성과 스냅샷에는 사용하지 않는다.
- 뒤 단계의 조기 알림 창이 열리면 앞 단계 catch-up 후보를 봉인해 같은 틱에서 준비 메시지가 두 개 전송되지 않게 했다.

## 이슈 및 인계

- 로컬에서 PyYAML이 없는 경우 간이 YAML 파서가 단계 목록을 읽지 못해 목록 지원을 추가했다. 운영 설치에는 `requirements.txt`의 PyYAML이 포함된다.
- 폰 실알림 수신은 이번 변경 후 아직 확인하지 않았다. 배포 후 단계별 수신과 dedup 로그를 확인해야 한다.
- 당일 일정만 계획하는 기존 설계상 출발보다 몇 시간 이른 단계가 전날로 넘어가면 해당 전날 알림은 생성되지 않는다. 이 경우는 별도 정책 결정이 필요하다.
