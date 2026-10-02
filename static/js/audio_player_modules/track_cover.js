// track_cover.js - 플레이어에 보여 줄 커버 주소
//
// 음악 모드(meta.is_music)는 곡별 커버(트랙 cover_image: 곡 파일의 내장 아트)를 쓴다. 차트 모음처럼
// 한 폴더 안에서 곡마다 원래 앨범이 다르기 때문이다. 오디오북은 앨범(책) 커버.

export function getTrackCoverImage(meta, track) {
  if (meta && meta.is_music && track && track.cover_image) return track.cover_image;
  return meta ? meta.cover_image : '';
}
