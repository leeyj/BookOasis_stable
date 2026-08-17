-- MariaDB Docker 최초 기동 시 4개 미디어 DB 및 유저 권한 자동 생성
CREATE DATABASE IF NOT EXISTS media_general CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_adult CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_audiobook CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_video CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

-- 와일드카드(패턴) GRANT: db 이름을 백틱 없이 지정하면 '_'와 '%'가 SQL 와일드카드로 해석되어,
-- 'media_'로 시작하는 모든 DB(지금 4개는 물론 앞으로 새 미디어 세션이 추가되며 생기는 DB까지)에
-- bookoasis 계정이 자동으로 권한을 갖는다. 새 DB가 추가될 때마다 이 파일을 갱신하고 기존
-- 설치본에 GRANT를 다시 실행해야 했던 문제(예: media_video 추가 시 기존 사용자
-- "Access denied for user 'bookoasis'@'%' to database 'media_video'")를 근본적으로 막기 위함.
GRANT ALL PRIVILEGES ON media_%.* TO 'bookoasis'@'%';

FLUSH PRIVILEGES;
