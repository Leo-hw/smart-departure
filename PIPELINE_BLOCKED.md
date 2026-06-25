# Pipeline Blocked — T-014 외부 트리거 검증 대기

T-014의 코드·가이드·워크플로우 설정 검증은 완료되었습니다.

남은 작업:

- 사용자가 fine-grained PAT를 발급하고 cron-job.org 5분 job을 설정
- 약 1시간 동안 `workflow_dispatch` run이 5분 간격으로 들어오는지 확인
- 미래 일정 1건으로 Discord 알림이 목표 시각 ±5분에 도착하는지 확인
- dispatch run 로그에 일정명/주소/원문 event ID가 없는지 확인

운영 검증 완료 전까지 T-009를 시작하지 않습니다.
