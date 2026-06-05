# T-008-report — 카카오 Maps 자동차 길찾기 연동

**완료일**: 2026-06-05  
**담당**: Codex

---

## AC 결과

| AC | 결과 | 비고 |
|----|------|------|
| `driving` provider를 카카오로 선택 | ✅ | transit/walking은 기존 Google 유지 |
| 카카오 Directions API 연동 | ✅ | 주소 검색 후 좌표 기반 추천 경로 조회 |
| `KAKAO_REST_API_KEY` 사용 | ✅ | 환경변수로만 참조 |
| 기존 `TravelResult` 반환 형식 유지 | ✅ | provider는 `kakao` |
| 실패 시 캐시, 기본값 30분 fallback | ✅ | 기존 6시간 캐시 정책 재사용 |
| driving 단위 테스트 추가 | ✅ | provider/API/캐시/기본값 검증 |

## 원래 기획과 달라진 점

- 없음

## 발생한 에러/이슈

- 없음

## 다음 작업자에게 전달할 주의사항

- GitHub Actions Secrets에 `KAKAO_REST_API_KEY`를 등록해야 실제 자동차 경로가 조회됨
- 카카오 주소 검색 결과가 없거나 API가 실패하면 정상적으로 fallback 결과가 반환됨
