-- MariaDB Docker 최초 기동 시 4개 미디어 DB 및 유저 권한 자동 생성
CREATE DATABASE IF NOT EXISTS media_general CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_adult CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_audiobook CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_video CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

-- 주의: "GRANT ... ON media_%.*" 같은 와일드카드 패턴은 GRANT 문 자체에서는 지원되지 않는다
-- (MariaDB 10.11 기준 실제 실행 시 ERROR 1064 SQL 구문 오류, mysql.db 시스템 테이블을 직접
-- 조작해야만 동작하는 저수준 트릭). 이 파일은 데이터 볼륨이 비어있는 최초 1회에만 실행되므로
-- 여기서는 현재 알려진 4개 DB에 개별 GRANT를 명시한다. 이후 새 DB가 추가돼도 기존 설치본은
-- docker-compose.mariadb.yml의 mariadb-grant-repair 서비스가 매 up마다 재실행되며 자동으로
-- 커버한다 (Access denied for user 'bookoasis'@'%' to database 'media_X' 문제 방지).
GRANT ALL PRIVILEGES ON media_general.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_adult.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_audiobook.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_video.* TO 'bookoasis'@'%';

FLUSH PRIVILEGES;
