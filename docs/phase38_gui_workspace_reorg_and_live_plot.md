# Phase 38: GUI Workspace Reorganization and Live Plot

## Goal

GUI가 버튼이 많고 역할이 섞여 보이는 문제를 줄인다. 측정 실행, 기기 상태,
이전 run 분석을 분리하고, plot preview와 live plot을 왜곡 없이 보여준다.

## Implemented

- Top-level GUI workspace를 세 탭으로 분리했다.
  - `Measurement`: recipe, plan, preflight, dry-run, hardware run, live plot
  - `Instruments`: Doctor와 기기 상태
  - `Analysis`: 이전 run 목록, summary, plot, metadata, report, feedback bundle
- `Doctor` 버튼과 상태창을 `Instruments` 탭으로 이동했다.
- 이전 run 불러오기, run folder/plot/report 열기, feedback bundle 생성을
  `Analysis` 탭으로 이동했다.
- 저장 plot preview는 SVG 파일을 화면에 늘려 붙이는 방식 대신 `points.csv`를
  읽어 Qt native plot widget으로 다시 그린다.
- Dry-run과 guarded Drain I-V hardware run 중 progress callback으로 들어오는
  point를 `Live Plot` 탭에 실시간 누적 표시한다.

## Design Notes

- Measurement runner, recipe, instrument layer는 변경하지 않았다.
- Live plot은 runner의 progress callback만 구독한다.
- Saved plot은 saved artifact SVG를 대체하지 않는다. 외부 파일 열기 버튼은
  기존 SVG artifact를 계속 열 수 있고, GUI 내부 preview만 CSV 기반으로 다시
  그린다.
- Matplotlib import가 현재 로컬 Python 환경의 Pillow 문제로 실패해서, GUI
  preview는 PySide `QPainter` 기반 경량 plot widget으로 구현했다. 이 방식은
  창 resize 때 좌표를 다시 계산하므로 이미지 왜곡이 생기지 않는다.

## User Checklist

- [ ] `ptm-gui`를 실행한다.
- [ ] 상단 workspace가 `Measurement`, `Instruments`, `Analysis`로 나뉘는지
  확인한다.
- [ ] `Instruments` 탭에서 `Doctor`를 실행하고 상태창이 업데이트되는지 확인한다.
- [ ] `Analysis` 탭에서 `Refresh Runs`, `Load Selected`로 이전 run을 불러온다.
- [ ] `Analysis > Plot`에서 창 크기를 바꿔도 plot이 찌그러지지 않는지 확인한다.
- [ ] `Measurement` 탭에서 dry-run을 실행하고 `Live Plot`에 point가 실시간으로
  누적되는지 확인한다.
