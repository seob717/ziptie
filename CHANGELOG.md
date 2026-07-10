# Changelog

## [0.3.0](https://github.com/seob717/ziptie/compare/v0.2.0...v0.3.0) (2026-07-10)


### Features

* rearm — 컴팩션 후 배달 마커 리셋으로 룰 재배달 ([f392aa3](https://github.com/seob717/ziptie/commit/f392aa3a414e1d7d6535fceeabb09a47271542e7))
* run.sh에 AP·AP12·ZP 압박 조건 추가 (DESIGN-pressure §3) ([c05269f](https://github.com/seob717/ziptie/commit/c05269f154fb5aa24974ae93fe302fd006cf8a65))
* SessionStart(compact) 훅 — 컴팩션 직후 재무장 배선 ([c4ec724](https://github.com/seob717/ziptie/commit/c4ec724455839614ece3f5a518cf1996473647cd))
* 강압박 실험용 압박 템플릿·rule 파일 추가 (DESIGN-pressure §2) ([05f8047](https://github.com/seob717/ziptie/commit/05f80478727c6171a3070e5040b704b5fdf5faf6))
* 강압박 채점 집계 — 런 표·조건별 CI·Fisher 출력 ([282e92f](https://github.com/seob717/ziptie/commit/282e92fdcb3583fb43185d51391c438b68517503))
* 강압박 채점 함수 P1~P6·C1~C2 + Wilson·Fisher (DESIGN-pressure §4) ([394dff3](https://github.com/seob717/ziptie/commit/394dff3f00d492abea4e4e4d8039f43545b3fdc7))
* 다중 룰 매칭 시 병합 배달 — N턴 소모 제거 ([7f6c3f9](https://github.com/seob717/ziptie/commit/7f6c3f93bbee927c1826dd3095e1869361169033))


### Bug Fixes

* enabled 오타값에 경고 — 무경고 활성 취급 제거 ([2b51976](https://github.com/seob717/ziptie/commit/2b5197644fbfea12900d2e5a68d16d30e91ba082))
* project_dir 해석 시 CLAUDE_PROJECT_DIR 우선 ([0857eeb](https://github.com/seob717/ziptie/commit/0857eeb68ce10d7e3ffd598454e0674ecf5d4e52))
* rearm — 세션 id "warned" 충돌로 재무장이 무동작하던 결함 ([1d4d7ba](https://github.com/seob717/ziptie/commit/1d4d7bae7e2690943fdb77e546cb6c6afcdaf23a))
* 룰 name 형식 검증 — 경로 문자로 인한 사일런트 룰 사망 방지 ([889d2ae](https://github.com/seob717/ziptie/commit/889d2ae22d6c5a473a4bf7e217e3c2f4cac06a93))
* 룰 소스 인코딩 오류가 병합 배치 전체를 무효화하지 않게 함 ([f51d831](https://github.com/seob717/ziptie/commit/f51d831e219646912615d4b5564ae9a8e915e9d4))
* 룰 파싱 경고를 세션당 1회로 제한 ([151275c](https://github.com/seob717/ziptie/commit/151275cd6634e8476edf066b669aef8c4bd61b0b))
* 비정상 session_id가 block 룰 평가를 무산시키지 않게 함 ([385953d](https://github.com/seob717/ziptie/commit/385953d49aaeeca9568dd2fd97edaaa6938796ea))
* 잘못된 정규식 경고도 세션당 1회로 제한 ([88bbf15](https://github.com/seob717/ziptie/commit/88bbf153f9101cd2831fa270d27c7d484947e8d6))
* 채점 스코핑 — 컴팩션 이후 산출물 강제·타임아웃 하드스톱 (사전등록 §2 운영화) ([3b0af15](https://github.com/seob717/ziptie/commit/3b0af15098e0a9194b5d37af1ed570a368d9d965))
* 채점기 — AC/ZC에서 summary.json 부재 시 레거시 폴백 차단(no_summary) ([d7c04f2](https://github.com/seob717/ziptie/commit/d7c04f2299d3be9dd5e3aaaa9d756868994569b0))
* 컴팩션 프로브 — 확인창 응답 정규식·기준1 계측·실행 기록 정합 ([e732f26](https://github.com/seob717/ziptie/commit/e732f263656ec56eb902bc7a2a604a519a879c6d))


### Tests

* pty 컴팩션 프로브 — /compact 유발·재무장 발화 검증 ([6a895a0](https://github.com/seob717/ziptie/commit/6a895a0b2d587212e9e1db1dbdb99a51c0a53e4e))
* 컴팩션 실험 러너 — AC/ZC 배선·관측 훅·2단 과제 ([16cd0e6](https://github.com/seob717/ziptie/commit/16cd0e6871d2dc34cf05dde279d8a953564959ab))


### Docs

* compile 커맨드 — $ARGUMENTS 명시, 검토 후 수정 절차, 파일명 규칙 ([f444717](https://github.com/seob717/ziptie/commit/f4447177225f8828aa9bcc90ca58154f4b88b2dc))
* README 갱신 — 병합 배달·name 규칙·강압박 재검증 결과·PreCompact 로드맵 ([dc887b0](https://github.com/seob717/ziptie/commit/dc887b0205b44dd958bc5a72859f29528c096216))
* 강압박 재검증 실험 설계 사전등록 (pilot/DESIGN-pressure.md) ([6d509a0](https://github.com/seob717/ziptie/commit/6d509a0440bb47dafb117e4672644e796b6c4084))
* 강압박 프리플라이트 결과 — 게이트 미통과, 2단계 진입 금지 (천장 재확인) ([1be53f9](https://github.com/seob717/ziptie/commit/1be53f9c722dc0937b503d2ef4e086d7120eeca4))
* 최종 리뷰 반영 — README 재무장·컴팩션 결과 갱신, P5 위반 양상 정밀화, rearm 무음 no-op ([e3f9e69](https://github.com/seob717/ziptie/commit/e3f9e6982411cfa9d887b0f8cfd009b378761d6c))
* 컴팩션 준수율 실험 사전등록 — 2단 과제·게이트·제외 규칙 고정 ([2771480](https://github.com/seob717/ziptie/commit/27714806175198f34695071ea62ba224331645e0))
* 컴팩션 프리플라이트 결과 — 게이트 미통과, 첫 균열(P5) 관측·재무장 3/3 검증 ([ec011fe](https://github.com/seob717/ziptie/commit/ec011fe8be95b4beb1ed98a443f3c10c4b10d8e1))

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
