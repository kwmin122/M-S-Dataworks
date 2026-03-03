현재 git 상태를 확인하고 다음을 순서대로 수행해줘:

1. **변경 사항 파악**
   ```bash
   git status
   git diff --stat
   git log --oneline -5
   ```

2. **커밋 메시지 작성**
   - Conventional Commits 형식: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
   - 한국어 또는 영어 (프로젝트 규칙에 따름)
   - 변경 이유를 간결하게 포함

3. **스테이징 & 커밋**
   - 관련 파일만 선택적으로 `git add`
   - `.env`, credentials, 임시 파일 등은 제외
   - 커밋 실행

4. **Push**
   - 현재 브랜치를 origin에 push
   - 새 브랜치면 `-u` 플래그 추가

5. **PR 생성**
   - `gh pr create` 사용
   - 제목: Conventional Commits 형식
   - 본문: 변경 이유, 주요 변경사항, 테스트 방법 포함
   - 라벨이 있으면 적절히 추가

커밋 전에 변경 내용을 요약해서 보여주고 확인을 받아줘.
