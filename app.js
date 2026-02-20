const RFX_TOOL_URL = "";
const RFX_PROXY_PATH = "/tool";
const ENABLE_PROXY_FALLBACK = false;

const i18n = {
  ko: {
    skipToContent: "본문으로 건너뛰기",
    navTrust: "신뢰",
    navFeatures: "기능",
    navProduct: "제품 실행",
    navFaq: "FAQ",
    heroEyebrow: "M&S 데이터웍스 엔터프라이즈 RFx 플랫폼",
    heroTitle: "복잡한 RFx, <br>근거 기반으로 빠르게 판단하는 Kira봇",
    heroDesc: "문서 분류부터 다중 패스 추출, 점수 근거 하이라이트까지. 제안 의사결정을 더 정확하고 빠르게 만듭니다.",
    heroPrimaryCta: "Kira봇 실행하기",
    heroSecondaryCta: "사용 흐름 보기",
    badgeRfx: "고신뢰 RFx",
    badgeProposal: "유사 제안서",
    badgeGeneral: "일반 문서",
    trustEyebrow: "Trust",
    trustTitle: "기업이 바로 쓰는 운영형 분석 경험",
    metric1: "반복 검토 시간 절감",
    metric2: "요건 누락 탐지 속도",
    metric3: "구조화 포맷 안정성 목표",
    metric4: "사내 지식 기반 질의응답",
    trustProof: "공공/민간 제안팀 · PMO · 품질관리 · 사업개발팀에서 활용",
    psEyebrow: "Problem to Solution",
    psTitle: "감으로 보던 제안 판단을, 근거 기반 프로세스로 전환",
    problemTitle: "기존 방식의 한계",
    problem1: "문서가 길수록 누락 가능성이 증가",
    problem2: "필수/권장 조건이 섞여 오판정 위험",
    problem3: "판단 근거를 찾는 데 시간이 오래 걸림",
    solutionTitle: "Kira봇으로 개선",
    solution1: "RFx/비RFx 게이트로 문서 유형 선분류",
    solution2: "다중 패스 추출과 중복 제거로 안정적 분석",
    solution3: "페이지 근거 하이라이트로 설명 가능한 결과 제공",
    featureEyebrow: "Core Features",
    featureTitle: "RFx 분석 정확도와 실무 속도를 동시에 확보",
    feature1Title: "RFx/비RFx 분류 게이트",
    feature1Desc: "연구보고서/일반문서 오판정을 줄이고 문서 성격에 맞는 분석 경로를 선택합니다.",
    feature2Title: "다중 패스 추출 + Merge/Dedup",
    feature2Desc: "대용량 문서를 분할 추출 후 통합해 요건 누락과 추출 변동성을 낮춥니다.",
    feature3Title: "모델 라우팅",
    feature3Desc: "문서 크기·난이도에 따라 모델을 자동 선택해 비용과 안정성을 함께 최적화합니다.",
    feature4Title: "근거 하이라이트",
    feature4Desc: "분석 결과마다 페이지 참조를 연결해 내부 검토와 승인 커뮤니케이션이 빨라집니다.",
    startEyebrow: "Start Now",
    startTitle: "3단계로 바로 시작하는 Kira봇",
    step1Title: "업로드",
    step1Desc: "회사 정보와 RFx 문서를 넣습니다.",
    step2Title: "분석",
    step2Desc: "요건 추출, 매칭, 점수 계산을 자동 수행합니다.",
    step3Title: "근거 확인",
    step3Desc: "페이지 기준 하이라이트로 최종 판단을 검증합니다.",
    startCta: "Kira봇 실행하기",
    appEyebrow: "Run Product",
    appTitle: "페이지 안에서 바로 실행되는 Kira봇",
    appDesc: "아래 임베드 영역에서 바로 사용하세요. 차단 환경에서는 새 탭 실행을 제공합니다.",
    appPending: "앱 로딩을 준비 중입니다...",
    fallbackMessage: "임베드가 제한된 환경입니다. 새 탭에서 제품을 실행하세요.",
    fallbackCta: "새 탭에서 열기",
    faqEyebrow: "FAQ & Security",
    faqTitle: "도입 전에 자주 묻는 질문",
    faq1Q: "Q. RFx가 아닌 문서도 사용할 수 있나요?",
    faq1A: "가능합니다. 문서 분류 게이트가 비RFx/유사 제안서를 구분해 참고용 분석 모드로 안내합니다.",
    faq2Q: "Q. 대용량 문서도 안정적으로 동작하나요?",
    faq2A: "다중 패스 추출과 모델 라우팅 정책으로 긴 문서에서 누락과 변동성을 줄이도록 설계되어 있습니다.",
    faq3Q: "Q. 보안과 개인정보는 어떻게 관리하나요?",
    faq3A: "로그인 기반 세션 관리, 사용자별 문서 저장 분리, 민감 정보 노출 방지 원칙을 적용합니다.",
    finalTitle: "제안 의사결정의 기준을, Kira봇으로 표준화하세요",
    finalDesc: "M&S 데이터웍스가 만드는 엔터프라이즈급 RFx 분석 경험을 지금 시작하세요.",
    finalCta: "Kira봇 바로 실행하기",
    footerLine: "Kira봇 | RFx Intelligence Platform"
  },
  en: {
    skipToContent: "Skip to content",
    navTrust: "Trust",
    navFeatures: "Features",
    navProduct: "Run Product",
    navFaq: "FAQ",
    heroEyebrow: "M&S DataWorks Enterprise RFx Platform",
    heroTitle: "KiraBot: Faster RFx decisions <br>with evidence you can trust",
    heroDesc: "From document classification to multi-pass extraction and page-level evidence highlights, make proposal decisions faster and more reliably.",
    heroPrimaryCta: "Run KiraBot",
    heroSecondaryCta: "See Workflow",
    badgeRfx: "High-confidence RFx",
    badgeProposal: "Proposal-like",
    badgeGeneral: "General Document",
    trustEyebrow: "Trust",
    trustTitle: "Operational analysis experience built for enterprise teams",
    metric1: "reduction in repetitive review time",
    metric2: "faster requirement gap detection",
    metric3: "target structured-output reliability",
    metric4: "internal Q&A coverage",
    trustProof: "Used by proposal teams, PMO, quality teams, and business development",
    psEyebrow: "Problem to Solution",
    psTitle: "Replace guesswork with evidence-based proposal decisions",
    problemTitle: "Legacy process limits",
    problem1: "Long documents increase omission risk",
    problem2: "Required vs recommended criteria can be misjudged",
    problem3: "Finding decision evidence takes too long",
    solutionTitle: "How KiraBot improves it",
    solution1: "Classifies RFx vs non-RFx before analysis",
    solution2: "Uses multi-pass extraction with dedup for stable outputs",
    solution3: "Provides page-level evidence highlights for explainable decisions",
    featureEyebrow: "Core Features",
    featureTitle: "Improve RFx accuracy and team speed at the same time",
    feature1Title: "RFx / non-RFx gate",
    feature1Desc: "Avoid false judgments for research and general documents with early document-type routing.",
    feature2Title: "Multi-pass extraction + Merge/Dedup",
    feature2Desc: "Split and merge large documents to reduce missing requirements and extraction variance.",
    feature3Title: "Model routing",
    feature3Desc: "Auto-select models by document size and complexity for cost and stability.",
    feature4Title: "Evidence highlighting",
    feature4Desc: "Connect conclusions to exact pages to speed up internal review and approvals.",
    startEyebrow: "Start Now",
    startTitle: "Start KiraBot in 3 practical steps",
    step1Title: "Upload",
    step1Desc: "Upload company docs and RFx documents.",
    step2Title: "Analyze",
    step2Desc: "Automatically extract requirements, run matching, and score.",
    step3Title: "Verify Evidence",
    step3Desc: "Validate final decisions with page-level highlights.",
    startCta: "Run KiraBot",
    appEyebrow: "Run Product",
    appTitle: "Run KiraBot directly inside this page",
    appDesc: "Use the embedded app below. If embedding is blocked, open it in a new tab.",
    appPending: "Preparing app loading...",
    fallbackMessage: "Embedding is restricted in this environment. Open the product in a new tab.",
    fallbackCta: "Open in New Tab",
    faqEyebrow: "FAQ & Security",
    faqTitle: "Questions teams ask before rollout",
    faq1Q: "Q. Can we use non-RFx documents too?",
    faq1A: "Yes. The document gate labels non-RFx/proposal-like content and guides users into reference analysis mode.",
    faq2Q: "Q. Is it stable for large documents?",
    faq2A: "Yes. Multi-pass extraction and model routing are designed to reduce misses and variance in long documents.",
    faq3Q: "Q. How are security and privacy handled?",
    faq3A: "We apply login-based sessions, per-user document separation, and strict handling of sensitive data.",
    finalTitle: "Standardize proposal decisions with KiraBot",
    finalDesc: "Start enterprise-grade RFx intelligence by M&S DataWorks today.",
    finalCta: "Run KiraBot Now",
    footerLine: "KiraBot | RFx Intelligence Platform"
  }
};

const langToggle = document.getElementById("langToggle");
const appFrameContainer = document.getElementById("appFrameContainer");
const appFrame = document.getElementById("rfxToolFrame");
const appLoading = document.getElementById("appLoading");
const appStatus = document.getElementById("appStatus");
const appFallback = document.getElementById("appFallback");
const fallbackLink = document.getElementById("fallbackLink");
const fallbackMessage = document.getElementById("fallbackMessage");

let iframeLoaded = false;
let iframeMounted = false;
let currentLang = localStorage.getItem("kira_lang") || "ko";

function resolveToolUrl() {
  const params = new URLSearchParams(window.location.search);
  const qsToolUrl = params.get("toolUrl");
  if (qsToolUrl) return qsToolUrl;

  if (RFX_TOOL_URL && !RFX_TOOL_URL.includes("YOUR-RFX-TOOL-DOMAIN")) {
    return RFX_TOOL_URL;
  }

  // 로컬 개발 기본값: landing(8080) -> streamlit(8501)
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return "http://localhost:8501";
  }

  if (ENABLE_PROXY_FALLBACK && window.location.origin.startsWith("http")) {
    return `${window.location.origin}${RFX_PROXY_PATH}`;
  }

  return "";
}

function setFallbackVisible(message) {
  appFallback.hidden = false;
  if (message) fallbackMessage.textContent = message;
}

function setStatus(text) {
  appStatus.textContent = text;
}

function mountIframeIfNeeded() {
  if (iframeMounted) return;
  iframeMounted = true;

  const targetUrl = resolveToolUrl();
  fallbackLink.href = targetUrl;

  if (!targetUrl) {
    setStatus(currentLang === "ko" ? "앱 URL 설정이 필요합니다." : "App URL configuration is required.");
    setFallbackVisible(currentLang === "ko" ? "app.js의 RFX_TOOL_URL을 실제 배포 URL로 바꿔주세요." : "Set RFX_TOOL_URL in app.js to your deployed app URL.");
    fallbackLink.href = "#";
    appLoading.style.display = "none";
    return;
  }

  setStatus(currentLang === "ko" ? "앱을 로딩 중입니다..." : "Loading product app...");

  const timeoutId = window.setTimeout(() => {
    if (!iframeLoaded) {
      setStatus(currentLang === "ko" ? "임베드 연결이 지연되고 있습니다." : "Embedded app loading is delayed.");
      setFallbackVisible(currentLang === "ko" ? "브라우저 정책으로 임베드가 제한될 수 있습니다. 새 탭 실행을 사용하세요." : "Embedding may be blocked by browser policy. Use open in new tab.");
      appLoading.style.display = "none";
    }
  }, 7000);

  appFrame.addEventListener("load", () => {
    iframeLoaded = true;
    window.clearTimeout(timeoutId);
    appFrameContainer.classList.add("loaded");
    appLoading.style.display = "none";
    setStatus(currentLang === "ko" ? "Kira봇이 준비되었습니다." : "KiraBot is ready.");
  }, { once: true });

  appFrame.addEventListener("error", () => {
    setStatus(currentLang === "ko" ? "임베드 로딩 실패" : "Embed loading failed");
    setFallbackVisible();
    appLoading.style.display = "none";
  });

  appFrame.src = targetUrl;
}

function setupLazyLoading() {
  if (!("IntersectionObserver" in window)) {
    mountIframeIfNeeded();
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        mountIframeIfNeeded();
        observer.disconnect();
      }
    });
  }, { rootMargin: "220px 0px" });

  observer.observe(appFrameContainer);
}

function applyLanguage(lang) {
  const dict = i18n[lang] || i18n.ko;
  document.documentElement.lang = lang === "ko" ? "ko" : "en";

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!dict[key]) return;
    el.innerHTML = dict[key];
  });

  langToggle.textContent = lang === "ko" ? "EN" : "KO";
  langToggle.setAttribute("aria-pressed", lang === "en" ? "true" : "false");
  localStorage.setItem("kira_lang", lang);
}

function setupLanguageToggle() {
  applyLanguage(currentLang);

  langToggle.addEventListener("click", () => {
    currentLang = currentLang === "ko" ? "en" : "ko";
    applyLanguage(currentLang);
    if (!iframeLoaded) {
      setStatus(currentLang === "ko" ? "앱 로딩을 준비 중입니다..." : "Preparing app loading...");
    }
  });
}

function setupSmoothScroll() {
  document.querySelectorAll("[data-scroll]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const selector = btn.getAttribute("data-scroll");
      const target = selector ? document.querySelector(selector) : null;
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function setupReveal() {
  const elements = Array.from(document.querySelectorAll(".reveal"));
  if (!("IntersectionObserver" in window)) {
    elements.forEach((el) => el.classList.add("revealed"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.18 });

  elements.forEach((el) => observer.observe(el));
}

function initYear() {
  const yearEl = document.getElementById("year");
  if (yearEl) {
    yearEl.textContent = String(new Date().getFullYear());
  }
}

function init() {
  initYear();
  setupLanguageToggle();
  setupSmoothScroll();
  setupReveal();
  setupLazyLoading();
}

window.addEventListener("DOMContentLoaded", init);
