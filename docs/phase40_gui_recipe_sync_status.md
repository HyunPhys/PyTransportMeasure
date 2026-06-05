# Phase 40: GUI Recipe Sync Status

## Goal

YAML과 Form의 관계를 GUI 안에서 명확히 보여준다. 실제 실행 기준은 항상
`Recipe YAML`이고, `Drain I-V Form`은 자주 쓰는 필드를 편집하기 위한 보조
화면이라는 점을 상태 메시지로 추적한다.

## Implemented

- `Recipe Tools` 아래에 recipe sync 상태 라벨을 추가했다.
- 기본 상태는 `Recipe YAML`이 실행 source라는 점을 표시한다.
- YAML editor를 직접 수정하면 다음을 안내한다.
  - YAML이 실행 source다.
  - Form도 같은 값으로 맞추려면 `YAML -> Form`을 누른다.
- Form 값을 수정하면 다음을 안내한다.
  - 아직 실행에 반영되지 않았다.
  - 실행에 쓰려면 `Form -> YAML`을 누른다.
- `Form -> YAML`을 누르면 YAML이 form 값으로 다시 생성되었고, 이 YAML이
  실행 source라는 점을 표시한다.

## User Checklist

- [ ] `ptm-gui`를 실행한다.
- [ ] `Recipe Tools` 아래에 execution source/status 문구가 보이는지 확인한다.
- [ ] `Recipe YAML`을 직접 수정하고 status가 `YAML edited`로 바뀌는지 확인한다.
- [ ] `Drain I-V Form`의 값을 수정하고 status가 `Form edited`로 바뀌는지 확인한다.
- [ ] `Form -> YAML`을 누르고 status가 YAML regenerated/source 상태로 바뀌는지
  확인한다.
