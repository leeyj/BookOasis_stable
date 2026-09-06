# 🎐 페이지 오버레이 마스코트 + LLM 챗 추천 플러그인 가이드

이 문서는 화면 한쪽(주로 우측 하단)에 캐릭터를 띄워두고, 클릭하면 채팅창이 열려 LLM과
대화하듯 도서를 추천받는 "오버레이 마스코트" 유형의 플러그인을 만드는 방법을 설명합니다.

> 전제 조건: 이 문서는 플러그인 공통 계약(`search`/`apply`, `config_schema`,
> `category_tab`, `get_dashboard_data` 등)을 이미 안다는 전제로 씁니다. 먼저
> [플러그인 개발 가이드](./guide_plugins.md)를 읽어주세요. 이 문서는 그 위에
> "오버레이 마스코트"라는 하나의 UI 패턴만 추가로 설명합니다.

완성된 예제는 [sample_plugins/metadata/reading_mate/](../sample_plugins/metadata/reading_mate/)에
있습니다. 아래 설명은 전부 이 샘플의 실제 코드를 인용합니다.

---

## 1. 먼저 알아야 할 것 - "진짜 화면 오버레이"는 아닙니다

VTube Studio처럼 브라우저 밖(바탕화면, 다른 프로그램 위)에 항상 떠 있는 OS 수준 오버레이는
**BookOasis 플러그인으로 만들 수 없습니다.** BookOasis는 브라우저에서 열어보는 웹앱이고,
플러그인은 그 웹 페이지 안에서만 동작하는 HTML/CSS/JS이기 때문입니다.

이 가이드가 다루는 건 **"BookOasis 페이지를 보고 있는 동안" 우측 하단에 떠 있는** 마스코트입니다.
그리고 코어에는 "앱이 켜질 때 모든 페이지에 무언가를 자동 주입하는" 훅이 없습니다
(`docs/guide_plugins.md` §5의 `category_tab`은 사이드바 탭을 사용자가 클릭했을 때만 마운트됩니다).

그래서 이 패턴은 다음 두 가지를 조합해 우회합니다.

1. **최초 마운트 지점**: 사용자가 사이드바에서 이 플러그인의 `category_tab`을 한 번 클릭하면
   `script.js`가 실행됩니다. 이때 마스코트 DOM을 만듭니다.
2. **`document.body`에 직접 부착**: 마스코트를 카테고리 탭 컨테이너
   (`#library-plugin-custom-view`) 안이 아니라 `document.body`에 붙입니다. 코어는 다른
   사이드바 탭으로 이동할 때 컨테이너의 `innerHTML`을 통째로 갈아치우는데,
   `document.body`에 붙은 요소는 그 대상이 아니므로 탭을 넘나들어도 계속 남아있습니다.

> ⚠️ 한계: 이 방식은 세션 중 사용자가 해당 플러그인 탭을 **한 번도 열지 않으면 마스코트가
> 전혀 뜨지 않습니다.** 그리고 브라우저를 새로고침하면 마스코트도 사라지고, 탭을 다시
> 한 번 열어야 재등장합니다. "부팅하자마자 항상 떠 있는 마스코트"는 지금 구조로는
> 불가능하니, 커뮤니티에 배포할 때 이 제약을 README에 명시하세요.

같은 트릭이 이미 `spotify_mood` 샘플의 플로팅 플레이어에도 쓰였습니다
([spotify_mood/script.js](../sample_plugins/metadata/spotify_mood/script.js)의
`ensureFloatingPlayer()`). 마스코트도 그 방식을 그대로 재사용합니다.

---

## 2. 디렉토리 구조

```text
plugins/metadata/
  reading_mate/
    __init__.py
    reading_mate.py
    VERSION
    index.html      # category_tab(사이드바) 전용 탭 - 설정 안내 + 마스코트 최초 마운트 지점
    style.css        # 위 탭 자체의 스타일 (마스코트 스타일은 아님, 3번 참고)
    script.js        # 마스코트 DOM 생성 + 채팅 로직
```

---

## 3. Python 제공자 클래스

`config_schema`로 LLM 접속 정보와 캐릭터 표시 정보를 운영자가 환경설정에서 입력하게 합니다.
API 키는 절대 프론트엔드로 내려가지 않고, 서버(이 클래스) 안에서만 사용됩니다.

```python
class ReadingMateMetadataProvider(BaseMetadataProvider):
    id = "reading_mate"
    name = "독서메이트 (오버레이 마스코트)"
    is_searchable = False

    config_schema = [
        {"key": "LLM_API_KEY", "label": "LLM API Key", "type": "password", "required": True},
        {"key": "LLM_BASE_URL", "label": "LLM API Base URL", "type": "text",
         "default": "https://api.openai.com/v1", "required": True},
        {"key": "LLM_MODEL", "label": "모델 이름", "type": "text", "default": "gpt-4o-mini"},
        {"key": "CHARACTER_NAME", "label": "캐릭터 이름", "type": "text", "default": "책비서"},
        {"key": "CHARACTER_IMAGE_URL", "label": "캐릭터 이미지 URL", "type": "text", "required": False},
    ]

    category_tab = {
        "title": "독서메이트",
        "icon": "fa-solid fa-comment-dots",
        "order": 95,
        "sessions": "general",  # 도서 추천용이므로 general에만 노출 (기본값도 general)
    }
```

`LLM_BASE_URL`을 노출해두면, OpenAI가 아니라 로컬 Ollama/LM Studio나 자체 LLM 게이트웨이처럼
`/chat/completions` 형식(OpenAI 호환)을 따르는 어떤 서비스도 그대로 붙일 수 있습니다.

`category_tab.sessions`에는 다음 값만 유효합니다.

| 값 | 의미 |
| :--- | :--- |
| 생략 | `general`에만 노출 (하위 호환 기본값) |
| `"all"` | `general`/`adult`/`audiobook`/`video` 4개 세션 전체 |
| `["general", "adult"]` 같은 리스트 | 지정한 세션에만 노출 |

도서 추천 마스코트는 오디오북/비디오/성인 서재에 노출할 이유가 없으므로 `"general"`만 씁니다.

---

## 4. 채팅 요청/응답 - `get_dashboard_data()`를 RPC로 재사용

플러그인은 자체 Flask 라우트를 만들 수 없습니다 (`docs/guide_plugins.md` §1 참고).
대신 코어가 이미 제공하는 `GET /api/media/dashboard/widgets/<plugin_id>/data` 엔드포인트가
`provider.get_dashboard_data(db_type, limit)`를 그대로 호출해주므로, 이걸 채팅 한 턴을
처리하는 범용 엔드포인트로 재사용합니다. 추가 파라미터(사용자 메시지, 대화 히스토리)는
`flask.request.args`의 쿼리 파라미터로 실어 보냅니다 (`spotify_mood`가 `mood`/`q`/`kind`를
같은 방식으로 받는 것과 동일한 패턴). GET 전용이라 몸값이 크지 않은 텍스트만 주고받는
채팅 용도에는 충분합니다.

```python
def get_dashboard_data(self, db_type, limit=10):
    cfg = self.get_plugin_config(db_type, default={}) or {}
    api_key = str(cfg.get("LLM_API_KEY") or "").strip()
    if not api_key:
        return {"success": False, "error": "LLM_API_KEY가 설정되지 않았습니다."}

    args = self._get_request_args()  # message, history를 request.args에서 파싱
    if not args["message"]:
        return {"success": True, "reply": "안녕! 어떤 책이 읽고 싶어?"}  # 최초 인사말

    library_sample = self._sample_library(db_type)          # 실제 서재 책 목록 일부
    system_prompt = self._build_system_prompt(..., library_sample)
    messages = [{"role": "system", "content": system_prompt}, *args["history"], {"role": "user", "content": args["message"]}]

    reply = self._call_llm(base_url, api_key, model, messages)  # 서버에서만 LLM 호출
    return {"success": True, "reply": reply}
```

핵심 포인트:

- **API 키는 서버에만 존재**합니다. 프론트는 `/api/media/dashboard/widgets/reading_mate/data`만
  호출하고, 요청/응답 어디에도 키가 노출되지 않습니다.
- **"내 서재에 실제로 있는 책"만 추천하도록 근거를 준다**: `self.get_db_gateway(db_type)`로
  `books` 테이블에서 최근 도서 제목/저자 샘플을 뽑아 시스템 프롬프트에 넣습니다
  (`SELECT title, author FROM books WHERE COALESCE(is_deleted,0)=0 ORDER BY id DESC LIMIT 30`).
  이렇게 하지 않으면 LLM이 서재에 없는 책을 지어내며 추천합니다.
- **비용/남용 방어**: 메시지 길이(`MAX_MESSAGE_CHARS`)와 히스토리 턴 수
  (`MAX_HISTORY_TURNS`)를 서버에서 강제로 자릅니다. 클라이언트가 보내는 값을 그대로
  믿지 마세요 - LLM 호출은 실제 비용이 발생합니다.

전체 구현은 [reading_mate.py](../sample_plugins/metadata/reading_mate/reading_mate.py)를 참고하세요.

---

## 5. 프론트엔드 - 마스코트 마운트 + 채팅 UI

`script.js`는 코어가 `new Function('pluginId', 'container', bundle.js)`로 감싸서 실행합니다.
즉 파일 최상단에서 `pluginId`/`container`가 이미 파라미터로 주어진 상태이며, 호스트 앱과
같은 DOM/JS 컨텍스트에서 동작합니다 (iframe 격리 없음).

### 5.1 마스코트 CSS는 `document.head`에 직접 주입한다

`style.css` 번들은 `category_tab` 컨테이너 안에 `<style id="plugin-custom-style-...">`로
주입되므로, 다른 탭으로 이동하면 컨테이너와 함께 사라집니다. 마스코트는 컨테이너 밖
(`document.body`)에 살아남아야 하므로, 마스코트 전용 CSS도 별도로 `document.head`에
직접 넣어 독립시킵니다.

```javascript
function ensureMascotStyle() {
  if (document.getElementById('reading-mate-mascot-style')) return;
  const style = document.createElement('style');
  style.id = 'reading-mate-mascot-style';
  style.textContent = `#reading-mate-mascot { position: fixed; right: 1.25rem; bottom: 1.25rem; ... }`;
  document.head.appendChild(style);
}
```

### 5.2 마스코트 DOM은 `document.body`에 붙이고, 이미 있으면 재사용한다

```javascript
function ensureMascot() {
  ensureMascotStyle();
  let host = document.getElementById('reading-mate-mascot');
  if (host) return host;          // 이미 떠 있으면 중복 생성하지 않음 (탭 재방문 대응)

  host = document.createElement('div');
  host.id = 'reading-mate-mascot';
  host.innerHTML = `...아바타 버튼 + 채팅 패널...`;
  document.body.appendChild(host);
  // 아바타 클릭 -> 채팅 패널 토글, 폼 submit -> sendMessage() 이벤트 리스너 연결
  return host;
}

ensureMascot();  // script.js가 실행될 때마다(탭을 열 때마다) 호출 - 이미 있으면 즉시 반환
```

### 5.3 채팅 전송

```javascript
function fetchReply(userText) {
  const params = new URLSearchParams({ message: userText || '', history: JSON.stringify(history) });
  fetch('/api/media/dashboard/widgets/reading_mate/data?' + params.toString())
    .then((res) => res.json())
    .then((data) => {
      if (!data.success) { appendBubble('assistant', data.error); return; }
      appendBubble('assistant', data.reply);
      history.push({ role: 'user', content: userText }, { role: 'assistant', content: data.reply });
    });
}
```

`history`는 모듈 스코프 변수(JS 클로저)에만 있습니다 - 탭을 옮겨도 유지되지만, 새로고침하면
사라집니다. 새로고침 후에도 대화를 이어가고 싶다면 `history`를 `sessionStorage`에
저장/복원하도록 확장하면 됩니다.

전체 구현은 [script.js](../sample_plugins/metadata/reading_mate/script.js)를 참고하세요.

---

## 6. 캐릭터 이미지

`CHARACTER_IMAGE_URL` 설정값이 있으면 백엔드 응답(`character_image_url`)에 실어 보내고,
프론트에서 아바타 버튼의 기본 이모지(📚)를 `<img>`로 교체합니다. 코어는 플러그인 폴더 안의
이미지 파일을 정적으로 서빙해주는 경로가 없으므로, 운영자가 외부 CDN/이미지 호스팅 URL을
직접 입력하는 구조입니다. 캐릭터 이미지를 샘플에 기본값으로 박아 배포할 경우, 그 이미지의
재배포 라이선스를 반드시 먼저 확인하세요.

---

## 7. 검증 체크리스트

- [ ] 사이드바에서 "독서메이트" 탭을 처음 클릭하면 우측 하단에 아바타가 뜨는가?
- [ ] 다른 탭(대시보드, 서재 목록 등)으로 이동해도 아바타가 계속 떠 있는가?
- [ ] 아바타를 클릭하면 채팅 패널이 열리고 인사말이 오는가?
- [ ] `LLM_API_KEY`를 비워둔 상태에서 메시지를 보내면 명확한 오류 메시지가 뜨는가?
- [ ] 새로고침 후 탭을 다시 열면 아바타가 재생성되는가 (중복 마운트 없이)?
- [ ] 네트워크 탭에서 응답에 API 키가 노출되지 않는가?
- [ ] 브라우저 콘솔에 `[Reading-Mate-Plugin]` 접두사 로그 외 에러가 없는가?

---

## 8. 이 패턴을 다른 용도로 응용하기

"마스코트 + 채팅"이 아니어도, `document.body` 앵커링 트릭 자체는 "탭을 넘나들어도 유지돼야
하는 미니 위젯"이면 무엇에든 재사용할 수 있습니다 (예: 재생 중인 오디오 미니 플레이어,
읽고 있던 책으로 돌아가기 버튼 등). 핵심은 항상 같습니다.

1. 위젯 DOM/CSS를 `category_tab` 컨테이너가 아니라 `document.head`/`document.body`에 직접 붙인다.
2. `script.js` 진입 시 `getElementById`로 기존 인스턴스가 있는지 먼저 확인해 중복 생성을 막는다.
3. 백엔드 통신이 필요하면 `get_dashboard_data()`를 범용 RPC로 재사용하고, `request.args`로
   파라미터를 받는다.
