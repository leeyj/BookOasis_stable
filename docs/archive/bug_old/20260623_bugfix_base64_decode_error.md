---
title: "Kavita YAML 표지 Base64 디코딩 에러 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-23
tags: [bug, backend, scanner, base64, cover_image]
---
# 버그 내역
스캔 작업 도중 `Kavita.yaml` 등의 메타데이터에서 추출한 표지 이미지의 Base64 문자열을 디코딩할 때 다음과 같은 에러가 발생하며 스캔 태스크가 예외 처리되는 현상 발생:
`binascii.Error: Invalid base64-encoded string: number of data characters (5) cannot be 1 more than a multiple of 4`

# 원인
일부 메타데이터에 포함된 Base64 텍스트 내에 `data:image/jpeg;base64,` 와 같은 Data URI Scheme 접두사가 포함되어 있거나, 포맷팅 과정에서 줄바꿈 문자열(`\n`, `\r`)이 섞여 들어가면서 문자열 길이가 4의 배수로 딱 떨어지지 않고 손상되어 파이썬의 `base64.b64decode` 함수가 실패함.

# 수정 사항
1. **`c:\project\media_server\tools\scanner\cover.py` 내의 `extract_cover_from_b64` 함수 개선**
   - `cover_b64` 문자열 내에 `,` 문자가 있다면 `data:image/...` 형태의 접두사를 제거하도록 split 로직 추가.
   - `.replace('\n', '').replace('\r', '').strip()`를 통해 개행 문자와 앞뒤 공백을 완벽히 제거.
   - 패딩(`=`) 추가 로직 이후에도 길이가 `4의 배수 + 1`이 되는 비정상 규격 문자열의 경우, 강제로 마지막 문자를 자르는(`cover_b64[:-1]`) 보정 로직을 추가하여 디코딩 에러를 원천 방지함.
2. **`c:\project\media_server\tools\lazy_scanner.py` 로직 동일 적용**
   - 기존에는 Lazy 스캐너 동작 시 개별 압축파일에서 바로 이미지를 추출하고 메타데이터(Kavita.yaml) 기반 Base64 추출을 건너뛰었으나, 이제 스캔 전 `parse_kavita_yaml`을 우선 로드하여 Base64 표지가 있다면 수정한 `extract_cover_from_b64` 로직을 타도록 구조를 개선함.

3. **`c:\project\media_server\tools\scanner\cover.py` 내의 `extract_cover_from_b64` WebP 변환 에러 Fallback 개선**
   - Base64 디코딩까지 정상 처리되었으나, 원본 데이터 자체가 너무 짧거나 손상되어 Pillow(PIL)에서 이미지 형식 식별에 실패(`cannot identify image file`)할 경우 기존에는 손상된 바이너리 파일을 그대로 저장하고 있었음.
   - 변환 및 식별 실패 시 `None`을 반환하도록 로직을 변경하여, 상위 호출자 로직에 의해 즉각 `get_series_cover_fallback`(압축 파일 내 직접 이미지 파싱) 로직으로 Fallback 될 수 있도록 안전장치 추가.
4. **`c:\project\media_server\tools\scanner\parser.py` Kavita.yaml FIRST 지시어 연동 기능 추가**
   - `Kavita.yaml` 파일 내에서 시리즈의 후속 권들이 표지 정보로 실제 Base64 데이터 대신 `cover: FIRST`와 같은 지시어(Placeholder)를 사용하는 경우가 발견됨.
   - 이러한 비정상 데이터가 Base64 디코더로 유입되는 것을 원천 차단함과 동시에, 파서 단에서 실제 Base64 데이터를 지닌 **첫 번째 커버를 찾아서 메모리에 임시 보관한 뒤, 이후 `FIRST` 지시어를 가진 후속 권들에 해당 첫 번째 커버의 Base64 데이터를 그대로 복제 연동**하도록 편의 기능을 대폭 강화함.

# 해결 사항
비정상적인 Base64 텍스트(접두사 포함, 개행 포함 등)가 유입되더라도 예외 없이 정상적으로 파싱하여 WebP 표지를 추출하고, 만약 데이터 자체가 손상된 가짜 Base64일 경우에는 부서진 이미지를 쓰지 않고 원본 파일에서 다시 표지를 추출하도록 완전히 자동화됨.
