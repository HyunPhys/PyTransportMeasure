# Phase 36: GUI Session Log

## Goal

GUI로 실험을 실행할 때 화면에 지나간 Doctor, Preflight, Progress, 오류
메시지를 파일로 남긴다. 연구실 노트북에서만 장비를 연결하는 운영 방식에서는
run folder만으로는 "GUI에서 그때 무엇을 봤는지"가 빠질 수 있으므로, GUI
세션 로그를 feedback bundle에 같이 넣을 수 있게 했다.

## Implemented

- GUI 시작 시 `data/gui_logs/<timestamp>_gui_session.log`를 만든다.
- GUI의 Session Log 탭에서 현재 세션 로그를 확인할 수 있다.
- `Open Log` 버튼으로 로그 폴더를 열 수 있다.
- 다음 이벤트가 로그에 append된다.
  - plan 생성
  - YAML validation
  - recipe load/save
  - Doctor 시작/결과/실패
  - Preflight 시작/결과/실패
  - dry-run 시작/진행/종료/실패
  - guarded Drain I-V hardware run 시작/진행/종료/실패/취소
  - saved run load
  - feedback bundle 생성
- GUI `Feedback Bundle` 버튼은 현재 GUI session log를 `extras/` 폴더에
  포함한다.
- CLI `ptm feedback-bundle`은 `--extra-file` 옵션으로 `doctor.json` 같은
  별도 진단 파일을 추가할 수 있다.

## Commands

```powershell
ptm feedback-bundle data\raw\<run_folder> --extra-file doctor.json
```

GUI에서는 `Feedback Bundle` 버튼을 누르면 현재 run folder와 GUI session log가
함께 ZIP으로 묶인다.

## Design Notes

- `pytransport.gui_session`은 PySide6에 의존하지 않는다.
- measurement runner는 session log를 알지 않는다.
- feedback bundle은 run artifact와 extra diagnostic file을 분리해서 보관한다.
- 이 구조는 Drain I-V뿐 아니라 향후 single-gate, AC/lock-in, pulse, 4-probe
  GUI 실행에도 그대로 사용할 수 있다.

## Lab Checklist

- [ ] `ptm-gui`를 실행한다.
- [ ] Session Log 탭에 `GUI session started`가 보이는지 확인한다.
- [ ] Doctor 또는 Dry Run을 실행한다.
- [ ] Session Log 탭에 실행 로그와 progress가 누적되는지 확인한다.
- [ ] Run이 끝난 뒤 `Feedback Bundle`을 누른다.
- [ ] 생성된 ZIP 안에 `extras/<gui_session_log>.log`가 들어있는지 확인한다.
