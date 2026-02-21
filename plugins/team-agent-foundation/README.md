# team-agent-foundation

팀 공통 에이전트 운영을 위한 Claude Code 플러그인 골격.

## 포함 컴포넌트
- `commands/think.md`: `/think` 깊은 사고 명령
- `agents/code-review-veteran.md`: 30년 경력 코드 리뷰 에이전트
- `agents/knowledge-curator.md`: 지식 축적/인계 에이전트
- `skills/maintainability-guardian/SKILL.md`: 유지보수성 스킬
- `skills/agent-memory-sync/SKILL.md`: 지식 동기화 스킬

## 구조
- `.claude-plugin/plugin.json`은 플러그인 메타데이터 파일
- `commands/`, `agents/`, `skills/`는 플러그인 루트에 위치

## 다음 단계
1. 플러그인 마켓플레이스/로컬 경로로 설치
2. `/help`, `/agents`에서 로딩 확인
3. 팀 규칙 변경 시 `agent.md`와 플러그인 문서를 함께 갱신
