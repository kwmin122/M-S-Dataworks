# Team Agent Standard (agent.md)

이 문서는 팀 에이전트가 같은 기준으로 협업하고, 지식을 재사용하도록 만드는 공용 표준이다.

## 1) 목적
- 작업 품질을 사람/에이전트/세션이 달라도 일정하게 유지한다.
- 재발하는 문제를 빠르게 해결할 수 있도록 지식을 축적한다.
- 리뷰, 설계, 구현, 운영 단계에서 동일한 체크리스트를 사용한다.

## 2) 공용 산출물
- `docs/agent-memory/decision-log.md`: 주요 의사결정 기록
- `docs/agent-memory/patterns.md`: 재사용 가능한 패턴
- `docs/agent-memory/failures.md`: 실패/회고/재발방지
- `docs/agent-memory/context.md`: 프로젝트 핵심 컨텍스트 요약

## 3) 협업 규칙
- 모든 에이전트는 작업 시작 전에 `docs/agent-memory/context.md`를 읽는다.
- 중요한 결정은 작업 종료 전에 `decision-log.md`에 1줄 이상 남긴다.
- 실패가 발생하면 원인, 영향, 재발방지안을 `failures.md`에 남긴다.
- 반복 가능한 해법은 `patterns.md`에 승격한다.

## 4) 핸드오프 템플릿
아래 템플릿으로 에이전트 간 인계한다.

```markdown
## Handoff
- 작업: <무엇을 했는지>
- 변경 파일: <파일 목록>
- 검증: <테스트/검증 결과>
- 리스크: <남은 위험>
- 다음 액션: <다음 담당이 즉시 할 일>
```

## 5) agent.md -> Skill -> Plugin 표준화
- 1단계(로컬 운영): `agent.md` + `.claude/agents/*.md` + `.claude/skills/*/SKILL.md`
- 2단계(팀 공유): 플러그인 루트(`plugins/<name>/`)에 `commands/`, `agents/`, `skills/` 배치
- 3단계(배포): `.claude-plugin/plugin.json` 버전 관리 + 팀 설정에 설치

## 6) 역할 분리 권장안
- 에이전트: 명확한 역할과 책임이 필요한 "행동 주체"(예: 코드 리뷰어)
- 스킬: 여러 역할이 공통으로 재사용하는 "방법론"(예: 유지보수성 체크리스트)

## 7) 품질 게이트
- 리뷰 결과는 심각도(Critical/High/Medium/Low)로 분류한다.
- 유지보수성 변경은 복잡도 감소 또는 가독성 개선 근거를 남긴다.
- 문서 없는 규칙은 팀 표준이 아니다. 반드시 `agent.md` 또는 스킬에 반영한다.
