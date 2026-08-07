-- MariaDB Docker 최초 기동 시 3개 미디어 DB 및 유저 권한 자동 생성
CREATE DATABASE IF NOT EXISTS media_general CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_adult CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_audiobook CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

GRANT ALL PRIVILEGES ON `media_general`.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON `media_adult`.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON `media_audiobook`.* TO 'bookoasis'@'%';

FLUSH PRIVILEGES;
