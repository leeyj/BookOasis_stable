# CHANGELOG
## v3.1.1
- (fix) 관리자가 영상 강좌 접근을 꺼 둔 사용자에게도 영상 강좌 메뉴가 보이던 문제 수정 — 로그인 때 이 권한 값을 읽지 않고 늘 허용으로 처리했음 | fix the video course menu showing for users whose video access was turned off — the value was not read at sign-in and always treated as allowed
- (fix) 권한 관리의 오디오북·영상 강좌 탭에 메뉴 전체 허용 스위치 추가 — 이 값이 꺼져 있으면 카테고리 권한을 줘도 메뉴가 안 보이는데 화면에서 바꿀 방법이 없었음 | add a menu access switch to the audiobook and video course tabs of permission management — when it was off the menu stayed hidden despite category permissions, and there was no way to change it on screen
- (fix) 권한 관리의 사용자 권한 변경(성인·다운로드·콘텐츠 등급·오디오북)이 영상 DB에는 저장되지 않던 문제 수정 | fix user permission changes (adult, download, content rating, audiobook) not being saved to the video DB
