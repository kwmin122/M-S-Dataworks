# KiraBot 에이전트 팀 운영 가이드

## 개요

3개 도구(크롬 Claude, Claude Code, Gemini)를 조합하여 사이트 QA → 수정 → 디자인 개선을 수행하는 에이전트 팀입니다.

## 도구별 역할

```
┌─────────────────────────────────────────────────────────────┐
│                      사용자 (오케스트레이터)                     │
│   각 도구 간 결과물을 전달하고 최종 판단을 내림                     │
└────┬──────────────────┬────────────────────┬────────────────┘
     │                  │                    │
     ▼                  ▼                    ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────────┐
│ 크롬 Claude  │  │ Claude Code  │  │ Gemini 3.1 Pro   │
│             │  │              │  │ (나노바나나 프로)   │
│ - 사이트 탐색 │  │ - 코드 수정   │  │ - 이미지 생성     │
│ - UX 리뷰   │  │ - 페이지 빌드  │  │ - 아이콘 생성     │
│ - 스크린샷   │  │ - 에셋 통합   │  │ - 일러스트 생성   │
│ - 이슈 작성  │  │ - 코드 리뷰   │  │                  │
└─────────────┘  └──────────────┘  └──────────────────┘

프롬프트:            서브에이전트:          프롬프트:
chrome-qa-           site-qa-optimizer     gemini-image-
reviewer.md          page-builder          generator.md
                     asset-integrator
                     code-review-veteran
```

## 실행 순서

### Step 1: 크롬 Claude로 QA 리뷰
```
도구: 크롬 Claude (브라우저)
입력: chrome-qa-reviewer.md 프롬프트
출력: 이슈 리포트 (마크다운)
```

### Step 2: Claude Code로 이슈 수정
```
도구: Claude Code
명령: /site-review 또는 직접 에이전트 호출
입력: Step 1의 이슈 리포트
출력: 수정된 코드
```

### Step 3: Gemini로 이미지 생성
```
도구: 나노바나나 프로 (Gemini 3.1 Pro)
입력: gemini-image-generator.md 템플릿
출력: 이미지 파일 (.webp, .svg, .png)
```

### Step 4: Claude Code로 이미지 통합
```
도구: Claude Code
에이전트: asset-integrator
입력: Step 3의 이미지 파일 경로
출력: 사이트에 이미지 반영
```

### Step 5: 최종 검증
```
도구: 크롬 Claude + Claude Code
확인: 수정 결과 재검증 + 코드 리뷰
```

## 파일 구조

```
.claude/
  agents/
    site-qa-optimizer.md    ← QA 리포트 기반 코드 수정
    page-builder.md         ← 신규 페이지/컴포넌트 구현
    asset-integrator.md     ← 이미지/에셋 통합
    code-review-veteran.md  ← 코드 품질 검증 (기존)
    knowledge-curator.md    ← 팀 메모리 관리 (기존)
  commands/
    site-review.md          ← /site-review 워크플로우 커맨드

docs/agent-prompts/
    README.md               ← 이 파일
    chrome-qa-reviewer.md   ← 크롬 Claude용 프롬프트
    gemini-image-generator.md ← Gemini용 이미지 생성 프롬프트
```
