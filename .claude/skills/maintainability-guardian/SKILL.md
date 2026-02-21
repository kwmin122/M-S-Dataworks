---
name: maintainability-guardian
description: Use when code quality drifts, technical debt increases, or refactoring decisions need a consistent maintainability standard.
---

# Maintainability Guardian

## Overview
유지보수성을 정량/정성 기준으로 점검해 리팩터링 우선순위를 정하는 스킬.

## When to Use
- 코드가 커지면서 변경 영향 범위 예측이 어려울 때
- 동일 버그가 반복될 때
- 함수/모듈이 과도하게 비대해졌을 때
- 리뷰에서 "읽기 어렵다" 피드백이 반복될 때

## Maintainability Rubric (0-2 each)
- Cohesion: 모듈 책임이 하나로 응집되어 있는가?
- Coupling: 외부 의존성이 최소화되어 있는가?
- Readability: 의도 파악이 빠르고 네이밍이 명확한가?
- Testability: 단위/통합 테스트 작성이 쉬운 구조인가?
- Change Safety: 변경 시 회귀를 감지할 장치가 있는가?

총점:
- 0-4: 즉시 개선 필요
- 5-7: 우선순위 중간
- 8-10: 유지 가능

## Workflow
1. Hotspot 식별: 최근 결함 빈도, 수정 횟수, 복잡도 높은 영역 파악
2. 루브릭 채점: 파일/모듈 단위로 0-2 점수 부여
3. 개선안 제시: 구조 개선, 테스트 보강, 경계 재정의 제안
4. 작게 실행: 한 번에 한 모듈만 변경
5. 검증 기록: 전/후 지표와 리스크를 남김

## Output Template
```markdown
## Maintainability Report
- Target: <module/file>
- Score: <n/10>
- Main Risks: <3개 이내>
- Refactor Plan: <작은 단계 1~3>
- Verification: <테스트/리뷰 기준>
```
