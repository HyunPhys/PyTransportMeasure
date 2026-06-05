# Phase 37: GUI Usability Pass

## Goal

GUI 피드백을 반영해 실험 중 자주 거슬리는 동작을 고쳤다. 이번 단계는 측정
코어를 바꾸지 않고, GUI 조작성만 개선한다.

## Implemented

- `Dry-run Model` 영역을 접을 수 있게 만들고 기본값을 collapsed로 변경했다.
- 상단 버튼을 두 줄로 나누어 창의 최소 폭이 과하게 커지지 않게 했다.
- recipe path와 plot preview의 최소 크기를 줄여 창 resize 제약을 완화했다.
- Session Log는 사용자가 맨 아래를 보고 있을 때만 새 로그를 따라간다.
- 사용자가 로그 중간을 보고 있으면 새 로그가 추가되어도 현재 위치를 유지한다.

## Verification

- GUI offscreen smoke test
- GUI app unit tests
- Full pytest suite

## User Checklist

- [ ] `ptm-gui`를 실행한다.
- [ ] `Dry-run Model`이 접힌 상태로 시작하는지 확인한다.
- [ ] `Dry-run Model` 제목을 눌러 열고 닫을 수 있는지 확인한다.
- [ ] 창의 폭과 높이를 줄이고 키울 수 있는지 확인한다.
- [ ] Session Log를 맨 아래에 둔 상태에서 새 로그가 아래로 따라오는지 확인한다.
- [ ] Session Log를 중간으로 올려둔 상태에서 새 로그가 생겨도 위치가 유지되는지
  확인한다.
