# Changelog

## [0.2.0](https://github.com/seob717/ziptie/compare/v0.1.0...v0.2.0) (2026-07-09)


### Features

* /ziptie:compile 커맨드 — 문서→트리거 바인딩 컴파일 ([ae216b0](https://github.com/seob717/ziptie/commit/ae216b054f02535cd9c1e5a6f76417b405f4daeb))
* /ziptie:report 커맨드 — 배달 집계 해설 ([5be7692](https://github.com/seob717/ziptie/commit/5be7692053c296cdef5e24c164706d0cf38283d4))
* compile·report 성공 시 star 유도 한 줄 추가 ([9a4d05f](https://github.com/seob717/ziptie/commit/9a4d05f462fc3714c7ce547c3fab3e5e3baa85c3))
* JIT 룰 주입 파일럿 하네스 (mock gh, A/B 러너, 채점기) ([e152047](https://github.com/seob717/ziptie/commit/e15204741c798e8e7436d8631647debe9e8e89e8))
* PreToolUse 엔트리포인트 — 실패 시 무조건 allow ([9dc1fc0](https://github.com/seob717/ziptie/commit/9dc1fc05a66c5b5b9ae3f58c19750627e3b40364))
* ziptie 플러그인 스캐폴드 (매니페스트 + 훅 등록) ([ac31131](https://github.com/seob717/ziptie/commit/ac31131a91cc1768f72a29ca10d1d646adf0a4cd))
* 로그 집계 — 룰별 배달 횟수, 죽은 룰 탐지 ([37d3acb](https://github.com/seob717/ziptie/commit/37d3acb658f7d0a4a8ad66dc46dd052351028226))
* 룰 파일 로더 — frontmatter 파싱, 안전 기본값(실패 시 무시) ([b046b54](https://github.com/seob717/ziptie/commit/b046b545b0df2f7c0852dbca6d19e0be0653784b))
* 마켓플레이스 매니페스트 추가 — /plugin 설치 지원 ([d87a3fd](https://github.com/seob717/ziptie/commit/d87a3fd8c3b74d1b214a98b71f9058412c3d6e48))
* 배달 엔진 — require-read/block, 세션 상태, 원본 동기화, JSONL 로깅 ([8c7737a](https://github.com/seob717/ziptie/commit/8c7737a3f43a3b6ae7f7d746ba2ac002ccc24e45))


### Bug Fixes

* 깨진 정규식 룰이 다른 룰 평가를 막지 않도록 룰별 격리 ([122a8b5](https://github.com/seob717/ziptie/commit/122a8b5b3a145dbce8f87f1b3e3c3ec89656b758))
* 미지원 strength는 무시 대신 require-read로 폴백 (스펙 §4.2 정합) ([b8d43bc](https://github.com/seob717/ziptie/commit/b8d43bc2ac826113d91cecff7e6d0e04d4aa5f08))
* 비-dict JSON 로그 라인에도 집계가 죽지 않도록 격리 ([2d9fc60](https://github.com/seob717/ziptie/commit/2d9fc6018c57e1fa42bbdeffc061b1b1f709310d))


### Tests

* E2E — 파일럿 Z 조건으로 ziptie 엔진 실측 (3/3) ([3337412](https://github.com/seob717/ziptie/commit/33374129ae584bdbfa85fed3ac147b0314fdf5e0))


### Docs

* README — 모토, 사용법, 실측 결과 ([260f21d](https://github.com/seob717/ziptie/commit/260f21dc3b4ad0ab02aac17494b44b4934e98297))
* README·커맨드 문서·plugin description 영문화 ([2ad69c8](https://github.com/seob717/ziptie/commit/2ad69c8dd364e34f159735db09fd37c9578d49fb))
* README에 star 유도 문구 추가 ([e1eb499](https://github.com/seob717/ziptie/commit/e1eb49942698437e3c5c3a5ab42503f5b8d7e0f2))
* README에 배지·Requirements·Development·Contributing·License 섹션 추가 ([d0ef80e](https://github.com/seob717/ziptie/commit/d0ef80e7cc651d550b500ea98281a621fd587cac))
