# CHANGELOG
## v3.1.2
- (fix) 볼 수 있는 카테고리가 하나도 없는 사용자에게 오디오북·영상 강좌 탭이 빈 채로 보이던 문제 수정 | fix the audiobook and video course tabs showing empty for users with no accessible category
- (fix) 카테고리 권한 확인 중 DB 오류가 나면 접근을 허용하던 문제 수정 — 이제 거부 | fix category permission checks allowing access when the DB check failed — now denied
- (improvement) 영상 강좌 폴더를 옮기거나 이름을 바꾸면 같은 강좌로 인식(이어 보기 기록 유지), 사라진 강좌는 목록에서 숨김 — 오디오북과 같은 규칙 | video courses keep their identity (and watch history) when their folder is moved or renamed, and vanished courses are hidden — same rules as audiobooks
- (improvement) 사용자 추가가 4개 DB에 같은 id로 저장되고, 중간에 실패하면 모두 되돌림 | adding a user now stores the same id in all four DBs and rolls back everywhere if one fails
- (fix) 대시보드 "읽는 중" 카드의 예비 열기 경로가 없는 함수를 불러 아무 일도 하지 않던 문제 수정 | fix the fallback open path of the dashboard "currently reading" card calling a missing function and doing nothing
- (feat) 독서메이트 샘플 플러그인 1.1.0 — 3D 캐릭터(VRM) 옵션 추가(기본 꺼짐, 기본 모델은 pixiv 공식 샘플), 책을 읽는 동안 마스코트 숨김 | Reading Mate sample plugin 1.1.0 — optional 3D character (VRM, off by default, pixiv's official sample model by default); the mascot hides while reading
## v3.1.1
- (fix) 관리자가 영상 강좌 접근을 꺼 둔 사용자에게도 영상 강좌 메뉴가 보이던 문제 수정 — 로그인 때 이 권한 값을 읽지 않고 늘 허용으로 처리했음 | fix the video course menu showing for users whose video access was turned off — the value was not read at sign-in and always treated as allowed
- (fix) 권한 관리의 오디오북·영상 강좌 탭에 메뉴 전체 허용 스위치 추가 — 이 값이 꺼져 있으면 카테고리 권한을 줘도 메뉴가 안 보이는데 화면에서 바꿀 방법이 없었음 | add a menu access switch to the audiobook and video course tabs of permission management — when it was off the menu stayed hidden despite category permissions, and there was no way to change it on screen
- (fix) 권한 관리의 사용자 권한 변경(성인·다운로드·콘텐츠 등급·오디오북)이 영상 DB에는 저장되지 않던 문제 수정 | fix user permission changes (adult, download, content rating, audiobook) not being saved to the video DB
