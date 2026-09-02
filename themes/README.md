# 커스텀 테마 작성 가이드

`themes/` 디렉토리에 `*.yaml` 파일을 넣으면 서버가 자동으로 읽어들여 대시보드 테마
선택 목록에 노출합니다. 별도 플러그인 설치나 코드 작성이 필요 없습니다.

## 파일 위치

`themes/내가만든테마.yaml` (파일명은 자유, 확장자는 `.yaml` 또는 `.yml`)

## 형식

```yaml
id: midnight_lavender          # 영소문자/숫자/-/_ 만, 32자 이내, 내장 테마 ID와 겹치면 안 됨
label: "🌸 미드나잇 라벤더"      # 테마 선택 드롭다운에 표시될 이름 (1~60자)
vars:
  app-bg-main: "#1a1625"
  app-bg-sidebar: "#211c30"
  app-bg-card: "#2a2438"
  app-bg-card-hover: "#332b45"
  app-text-primary: "#f3f0fa"
  app-text-muted: "#a89cc8"
  app-text-secondary: "#c9bce0"
  app-accent: "#c084fc"
  app-accent-hover: "#d8b4fe"
  app-accent-contrast: "#1a1625"
  app-border: "#3d3450"
  app-border-light: "#332b45"
  app-input-bg: "#211c30"
  app-panel-rgb: "42, 36, 56"
  app-panel-border-rgb: "255, 255, 255"
```

## 규칙 (하나라도 안 맞으면 파일 전체가 무시됩니다)

- `id` / `label` / `vars` 세 키가 모두 있어야 합니다.
- `vars`에는 위 15개 키가 **전부** 있어야 하고, 그 외의 키는 허용되지 않습니다
  (임의 CSS 속성이나 `box-shadow`/`filter` 값은 지원하지 않습니다 — 보안상 원천 차단).
- `app-panel-rgb` / `app-panel-border-rgb`만 `"R, G, B"` 형식(0~255 정수 3개, 알파 없음)이고,
  나머지 13개는 전부 `#rgb` / `#rrggbb` / `#rrggbbaa` 형식의 hex 색상이어야 합니다.
- `id`는 기존 8개 내장 테마(`purple`/`dark`/`light`/`sepia`/`blue`/`aquamarine`/`ironman`/`epaper`)
  이름과 겹칠 수 없습니다.

## 각 변수의 역할 (참고용)

| 변수 | 역할 |
|---|---|
| `app-bg-main` | 페이지 전체 배경 |
| `app-bg-sidebar` | 사이드바 배경 |
| `app-bg-card` | 카드/패널 배경 |
| `app-bg-card-hover` | 카드 hover 시 배경 |
| `app-text-primary` | 기본 텍스트색 |
| `app-text-muted` | 보조/뮤트 텍스트색 |
| `app-text-secondary` | 부제/보조 강조 텍스트색 |
| `app-accent` | 브랜드 강조색 (버튼, 아이콘, 링크 등) |
| `app-accent-hover` | accent의 밝은 변형 (hover, 강조 텍스트) |
| `app-accent-contrast` | **불투명 accent 배경 위에 올라가는 글자색.** accent가 밝은 색이면 어두운 값을, 어두운 색이면 흰색을 넣어야 글자가 안 보이는 사고를 막을 수 있습니다 |
| `app-border` / `app-border-light` | 테두리색 (진한/연한) |
| `app-input-bg` | input/select 배경 |
| `app-panel-rgb` | 반투명 패널 배경의 RGB (알파 없이, `rgba(var(--app-panel-rgb), 0.6)` 형태로 쓰임) |
| `app-panel-border-rgb` | 반투명 패널 테두리의 RGB |

## 적용 및 재스캔

파일을 넣거나 수정한 뒤 **서버 재시작 없이** 설정 > 일반 탭의 "커스텀 테마 다시 스캔"
버튼(관리자 전용)을 누르면 즉시 반영됩니다. 검증에 실패한 파일은 그 버튼을 누른 결과
화면에 파일명과 실패 사유가 표시됩니다.
