"""
Streamlit UI 토큰 + 공통 CSS.

디자인 목표:
- 밝은 블루/화이트 엔터프라이즈 톤
- 카드형 정보 구조
- 상태 배지 가독성 강화
"""

from __future__ import annotations


UI_TOKENS: dict[str, str] = {
    "color_primary": "#2F6FEB",
    "color_primary_dark": "#1D4ED8",
    "color_text_main": "#0F1E36",
    "color_text_subtle": "#4A5B75",
    "color_bg_page": "#F4F7FD",
    "color_bg_card": "#FFFFFF",
    "color_border": "#D8E2F1",
    "color_success": "#1B7F3B",
    "color_warning": "#A05A00",
    "color_neutral": "#52606D",
    "shadow_card": "0 8px 24px rgba(15, 30, 54, 0.06)",
}


def build_streamlit_css() -> str:
    """앱 공통 CSS를 반환한다."""
    t = UI_TOKENS
    return f"""
<style>
    :root {{
        --kira-primary: {t["color_primary"]};
        --kira-primary-dark: {t["color_primary_dark"]};
        --kira-text-main: {t["color_text_main"]};
        --kira-text-subtle: {t["color_text_subtle"]};
        --kira-bg-page: {t["color_bg_page"]};
        --kira-bg-card: {t["color_bg_card"]};
        --kira-border: {t["color_border"]};
        --kira-success: {t["color_success"]};
        --kira-warning: {t["color_warning"]};
        --kira-neutral: {t["color_neutral"]};
        --kira-card-shadow: {t["shadow_card"]};
    }}

    .stApp {{
        background: linear-gradient(180deg, #eef3fd 0%, #f7f9fe 100%);
    }}

    .main .block-container {{
        padding: 1rem 1.5rem;
        max-width: 100%;
    }}

    .main-header {{
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, var(--kira-primary-dark) 0%, var(--kira-primary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3em;
    }}

    .kira-status-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin: 8px 0 12px 0;
    }}

    .kira-status-card {{
        background: var(--kira-bg-card);
        border: 1px solid var(--kira-border);
        border-radius: 12px;
        padding: 10px 12px;
        box-shadow: var(--kira-card-shadow);
        min-height: 72px;
    }}

    .kira-status-label {{
        font-size: 0.75rem;
        color: var(--kira-text-subtle);
        margin-bottom: 6px;
        font-weight: 600;
    }}

    .kira-status-value {{
        font-size: 0.9rem;
        color: var(--kira-text-main);
        font-weight: 700;
        line-height: 1.2;
    }}

    .kira-section-card {{
        background: var(--kira-bg-card);
        border: 1px solid var(--kira-border);
        border-radius: 14px;
        padding: 14px;
        box-shadow: var(--kira-card-shadow);
        margin-bottom: 10px;
    }}

    .ref-badge {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #fff8e1;
        border: 1px solid #ffd54f;
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.82em;
        color: #f57f17;
        font-weight: 600;
        margin: 0 2px;
    }}

    .highlight-info {{
        background: #fff8e1;
        border-left: 3px solid #ffd54f;
        padding: 8px 12px;
        border-radius: 0 6px 6px 0;
        margin: 8px 0;
        font-size: 0.85em;
        color: #5d4037;
    }}

    section[data-testid="stSidebar"] {{
        width: 340px;
    }}

    .stChatInput {{
        position: sticky;
        bottom: 0;
    }}

    .stButton > button {{
        font-size: 0.84em;
        padding: 8px 10px;
        white-space: normal;
        word-break: keep-all;
        overflow-wrap: anywhere;
        line-height: 1.35;
        text-align: left;
        min-height: 44px;
    }}

    @media (max-width: 1200px) {{
        .kira-status-grid {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
    }}

    @media (max-width: 768px) {{
        .main .block-container {{
            padding: 0.75rem 0.7rem;
        }}
        section[data-testid="stSidebar"] {{
            width: 100%;
        }}
        .kira-status-grid {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
    }}
</style>
"""
