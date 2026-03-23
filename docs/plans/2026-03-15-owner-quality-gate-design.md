# Owner Quality Gate Design

## 목적

`owner-quality-gate`는 코드리뷰, 설계리뷰, 구현 진행상황 점검 시 다음 두 질문에 강제로 답하게 하는 전용 리뷰 스킬이다.

1. 이 변경이 실제로 제품 품질을 높이는 구조적 진전인가?
2. 아니면 테스트 통과, 상태값 변경, 예외 흡수 같은 우회성 해결이 남아 있는가?

이 스킬은 일반 코드리뷰를 대체하지 않는다. 대신 `requesting-code-review`, `receiving-code-review`, `owner-operator-thinking` 위에 올라가는 품질 판정 게이트 역할을 한다.

## 왜 별도 스킬인가

- `owner-operator-thinking`은 원칙은 강하지만 출력 형식이 넓다.
- 일반 코드리뷰 스킬은 버그와 리스크를 찾는 데 초점이 있고, `구조적 품질 vs 우회성 해결` 분류를 강제하지 않는다.
- 현재 프로젝트는 `테스트는 녹색이지만 사용자 경로나 의미론은 아직 닫히지 않은 상태`가 자주 발생한다.

따라서 이 스킬은 아래를 별도로 고정한다.

- `Root fix / Mitigation / Suppression` 분류
- end-to-end 사용자 경로 폐쇄 여부 점검
- 의미를 속이는 해결 여부 탐지
- 잔여 리스크와 오너 판단 강제

## 언제 쓰는가

- “이제 진짜 되는 상태인가?”를 판단할 때
- “퀄리티 높게 가고 있는가?”를 오너 관점에서 볼 때
- 완료 보고 전에 `로컬 성공`과 `실제 사용자 성공`을 구분해야 할 때
- 리뷰에서 “우회해서 해결한 것 아닌가?”를 확인할 때

## 출력 계약

스킬 사용 결과는 항상 다음 순서를 따른다.

1. `Findings`
2. `Root fix / Mitigation / Suppression`
3. `End-to-end status`
4. `Residual risk`
5. `Owner judgment`

## 핵심 체크포인트

### 1. 사용자 가치 경로

변경이 실제 사용자의 핵심 경로를 닫았는지 본다.

예:

- API는 생겼지만 router 미포함
- DB 기록은 되지만 UI 진입점 없음
- quality report는 나오지만 제출 가능성 판단에는 안 연결됨

### 2. 의미론 보존

이름만 바꿔서 문제를 덮는지 본다.

예:

- `uploaded`를 바로 `verified`로 승격
- `hwpx` 요청인데 실제로는 `docx` 바이트 업로드
- fallback이 사용자/DB 의미와 충돌

### 3. 계약 진실성

스키마와 인터페이스는 생겼지만 실제 값이 더미인지 본다.

예:

- `similar_projects = []`
- `matching_personnel = []`
- `pass_threshold = 0.0`
- `required_checks` 하드코딩

### 4. 검증 진실성

테스트가 실제 실패 경로를 잡는지 본다.

예:

- 모델 필드만 assert하고 외부 시스템 검증 안 함
- mock만 성공하고 실제 storage/head 확인 없음
- 구조는 맞지만 end-to-end 시나리오 없음

## 비목표

- 스타일, 성능, 리팩터링 품질 전반을 모두 대신 평가하지 않는다.
- 구현을 직접 수행하는 스킬이 아니다.
- 배포 승인 스킬이 아니다.

## 추천 사용 흐름

1. 코드/설계/테스트를 읽는다.
2. 사용자 핵심 경로를 한 줄로 정의한다.
3. 각 수정 항목을 `root fix`, `mitigation`, `suppression`으로 분류한다.
4. end-to-end 폐쇄 여부를 말한다.
5. 남은 우회와 잔여 리스크를 숨기지 않는다.
6. 최종적으로 `execution-ready`, `not ready`, `partial progress` 중 하나로 판정한다.

## 산출물

이 설계에 따라 실제 스킬은 아래를 포함한다.

- 짧은 트리거 설명
- 품질 게이트 질문
- 우회성 해결 레드플래그
- 출력 템플릿
- 금지 규칙
