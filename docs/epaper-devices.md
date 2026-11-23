# e-paper 기기 추가하기 (기여 가이드)

BookOasis는 e-paper 리더용으로 EPUB·TXT를 정리한 변환본을 만든다. 어떤 기기에 어떤 변환을 쓸지는 두 표가 정한다.

| 표 | 파일 | 뜻 | 바꾸면 |
| --- | --- | --- | --- |
| 프로필 | `services/epaper/profile.py` | 화면 등급별 변환 수치(그림 크기, 그림 형식) | 그 프로필을 쓰는 모든 사용자의 변환본·digest가 바뀐다 |
| 모델 | `services/epaper/devices.py` | 기기 모델 → 프로필 연결, 설정 화면에 보이는 이름 | 그 모델 사용자만 영향을 받는다 |

대부분의 요청은 **모델 표에 한 줄을 더하는 것**으로 끝난다. 새 프로필은 거의 필요 없다.

## 1. 모델 한 줄 추가

`services/epaper/devices.py` 의 `MODELS` 에 `DeviceModel(...)` 하나를 더한다.

```python
DeviceModel('pocketbook-verse', 'PocketBook Verse', 'PocketBook Verse', 'gray-low', 'both', False,
            'https://example.invalid/spec (1024x758)'),
```

| 칸 | 규칙 |
| --- | --- |
| 모델 id | 사용자 설정에 저장되는 값이라 **한번 정하면 바꾸지 않는다**. 소문자·숫자·`-` 만, 점 금지, `local-` 로 시작하지 않는다 |
| 이름 / 영어 이름 | 화면 표시용. 언제든 고쳐도 된다 |
| 프로필 | 아래 2절 기준으로 고른다 |
| 쓰는 곳 | `web`(웹 메뉴 "기기용 받기"만), `feed`(기기 피드만), `both` |
| 실기기 확인 | 실제 기기로 변환본을 열어 봤으면 `True` |
| 사양 출처 | **필수.** 화면 짧은 변의 픽셀 수와 컬러 여부가 적힌 공식 자료(제조사 페이지, SDK 등) |

같은 화면을 쓰는 모델은 한 줄로 묶어도 된다(예: `kobo-1072` = Clara HD / 2E / BW).

## 2. 프로필 고르는 기준

1. **컬러 화면** → `color-hd`
2. **Kindle 항목**은 예외다. `kindle-send` 하나만 두고 `web` 전용, `color-hd` 로 고정한다(순정 Kindle은 Send to Kindle로만 EPUB을 받고 Amazon이 다시 변환한다). KOReader를 쓰는 Kindle은 범용 항목(`generic-hd` / `generic-low`)을 쓴다.
3. 나머지 흑백 기기: 화면 **짧은 변이 758px 이하** → `gray-low`, 넘으면 → `gray-hd`
4. 그림을 1비트로 보내야 하는 저사양 기기(ESP32 계열 등)는 해상도별 프로필(`v1`, `x4`, `x3`)을 쓴다. 해상도가 새로우면 새 프로필이 필요하다(3절).

출처가 없는 사양은 넣지 않는다. "킨들 10세대"처럼 이름 하나가 여러 기기(기본형 / Paperwhite / Oasis)를 가리킬 수 있으니 정확한 모델명으로 확인한다.

## 3. 프로필을 고치거나 새로 만들 때

- 값을 고치면 그 프로필의 `revision` 을 올린다. id는 그대로 둔다. 캐시가 그 프로필의 변환본만 다시 만든다.
- 새 id는 화면 등급 자체가 새로 필요할 때만 만든다(새 저사양 해상도, 짧은 변 758px 이하 컬러 등). id는 OPF·HTTP 헤더·캐시 키로 공개되어 영구다.
- 테스트(`tests/test_epaper_converter.py`)가 결정적 변환, 구조 보존, id 규칙, 모델 표의 프로필 존재를 확인한다. `.venv` 의 Python으로 `python -m pytest tests` 를 돌린다.
- 모든 프로필에 같은 구조 보존 규칙(`docs/device-api.md` §5.1)이 적용된다. 예외 프로필은 두지 않는다.

## 4. 리뷰 기준

- 모델 추가: 사양 출처와 2절 기준이 맞으면 된다.
- **모델을 다른 프로필로 옮기는 PR**은 프로필 값 수정과 같은 무게로 본다. 그 모델 사용자의 변환본·digest가 바뀌기 때문이다(EPUB 진행 기록은 이어진다). 출처(짧은 변 픽셀 수, 컬러 여부)가 필수다.
- 모델 id 변경은 받지 않는다. 이름만 고친다.

요청이 PR·Discord로 오면 이 문서를 안내한다. 기기 API 명세는 `docs/device-api.md` 에 있다.
