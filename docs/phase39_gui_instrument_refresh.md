# Phase 39: GUI Instrument Refresh and Communication Test

## Goal

`Instruments` workspace가 실제로 현재 연결 상태를 확인하는 장소가 되도록 한다.
사용자는 GUI 안에서 VISA resource 목록을 새로고침하고, 선택한 주소에 대해
Keithley 통신 테스트를 실행할 수 있어야 한다.

## Implemented

- `Refresh Instruments` 버튼을 추가했다.
  - PyVISA resource 목록을 읽어 `Instruments` 상태창에 표시한다.
  - 발견된 resource를 주소 선택 콤보박스에 채운다.
  - 현재 recipe의 VISA address도 fallback 후보로 유지한다.
- `Test Selected Address` 버튼을 추가했다.
  - 선택한 VISA address에 대해 Doctor 기반 통신 probe를 실행한다.
  - address 발견 여부, `*IDN?`, command language 등 probe 결과를 표시한다.
- `Full Doctor` 버튼은 기존 Doctor 기능을 유지하되, 이름을 명확히 바꿨다.
- recipe tool 버튼 이름을 구체화했다.
  - `Open Recipe File`: recipe path의 YAML 파일을 editor로 읽어온다.
  - `Check YAML`: 현재 editor YAML을 schema/safety 기준으로 검증한다.
  - `Save YAML As`: 현재 editor YAML을 파일로 저장한다.
  - `YAML -> Form`: 현재 YAML 값을 structured Drain I-V form에 복사한다.
  - `Form -> YAML`: form 값을 YAML editor로 다시 생성한다.

## User Checklist

- [ ] `ptm-gui`를 실행한다.
- [ ] `Instruments` 탭을 연다.
- [ ] `Refresh Instruments`를 누른다.
- [ ] 연결된 VISA resource가 주소 선택 목록과 상태창에 나타나는지 확인한다.
- [ ] 테스트할 주소를 선택한다.
- [ ] `Test Selected Address`를 누른다.
- [ ] Keithley가 연결된 주소라면 `OK: True`, `Address found: True`, probe 정보가
  표시되는지 확인한다.
- [ ] recipe 버튼 이름이 `Open Recipe File`, `Check YAML`, `Save YAML As`,
  `YAML -> Form`, `Form -> YAML`로 표시되는지 확인한다.
