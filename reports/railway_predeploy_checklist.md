# Railway 배포 전 E2E 체크리스트 실행 결과

- 실행 시각: 2026-02-15T19:38:24.425764+09:00

| 항목 | 상태 | 상세 |
|------|------|------|
| Python 문법 검사 | PASS | 핵심 파일 py_compile 통과 |
| 핵심 회귀 테스트 | PASS | 17 passed in 1.38s |
| PDF viewer import | FAIL | Traceback (most recent call last):   File "<string>", line 1, in <module>     import streamlit_pdf_viewer; print('ok')     ^^^^^^^^^^^^^^^^^^^^^^^^^^^ ModuleNotFoundError: No module named 'streamlit_pdf_viewer' |
| 실서버 URL 점검 | SKIP | --base-url 미지정 |
