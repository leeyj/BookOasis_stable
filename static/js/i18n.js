// -*- coding: utf-8 -*-
/**
 * BookOasis i18n (국제화/다국어 지원) 엔진 v1.0
 */

const i18n = {
    currentLang: 'ko',
    availableLanguages: [],
    dictionary: {},

    /**
     * i18n 시스템 초기화
     */
    async init() {
        // 1. 캐싱된 언어 혹은 브라우저 기본 언어 감지
        const savedLang = localStorage.getItem('bookoasis_lang');
        if (savedLang) {
            this.currentLang = savedLang;
        } else {
            const browserLang = navigator.language || navigator.userLanguage;
            this.currentLang = browserLang.split('-')[0] || 'ko';
        }

        try {
            // 2. 백엔드로부터 활성화된 동적 언어팩 목록 로드
            const response = await fetch('/api/i18n/languages');
            const data = await response.json();
            if (data.success) {
                this.availableLanguages = data.languages;
            }
        } catch (e) {
            console.error('[i18n] Failed to fetch language list', e);
            // API 로드 실패 시 기본값 세팅
            this.availableLanguages = [
                { code: 'ko', name: '한국어' },
                { code: 'en', name: 'English' }
            ];
        }

        // 감지된 언어가 스캔된 목록에 없으면 기본값(ko)으로 세팅
        if (!this.availableLanguages.some(l => l.code === this.currentLang)) {
            this.currentLang = 'ko';
        }

        // 3. 현재 언어팩 사전 데이터 로드
        await this.loadLanguagePack(this.currentLang);
    },

    /**
     * 특정 언어의 사전 데이터를 비동기로 로드
     */
    async loadLanguagePack(lang) {
        try {
            const response = await fetch(`/static/i18n/${lang}.json`);
            if (response.ok) {
                this.dictionary = await response.json();
                this.currentLang = lang;
                localStorage.setItem('bookoasis_lang', lang);
            } else {
                throw new Error(`Status ${response.status}`);
            }
        } catch (e) {
            console.error(`[i18n] Failed to load language pack for: ${lang}`, e);
            // 로드 실패 시 한국어 파일로 롤백 시도
            if (lang !== 'ko') {
                await this.loadLanguagePack('ko');
            }
        }
    },

    /**
     * 키 값을 기준으로 번역 데이터 획득 및 텍스트 템플릿 보간
     * @param {string} key - 점(.) 구분자로 연결된 번역 키 (예: 'login.title')
     * @param {object} variables - 템플릿 문자열 보간용 변수 객체
     */
    t(key, variables = {}) {
        const keys = key.split('.');
        let value = this.dictionary;
        
        for (const k of keys) {
            if (value && value[k] !== undefined) {
                value = value[k];
            } else {
                return key; // 키가 사전에 없으면 키 자체를 반환
            }
        }

        if (typeof value !== 'string') {
            return key;
        }

        // 변수 보간 처리 {variable}
        let result = value;
        for (const [vKey, vVal] of Object.entries(variables)) {
            result = result.replace(new RegExp(`{${vKey}}`, 'g'), vVal);
        }
        return result.replace(/\\n/g, '\n');
    },

    /**
     * data-i18n 속성이 매핑된 모든 DOM 요소를 일괄 자동 번역 적용
     */
    translateDOM(root = document) {
        // 1. 일반 콘텐츠 번역 (HTML 태그 포함 여부에 따라 분기)
        root.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                const translated = this.t(key);
                // 번역문에 HTML 태그가 포함되어 있다면 innerHTML로 안전하게 삽입
                if (translated.includes('<') && translated.includes('>')) {
                    el.innerHTML = translated;
                } else {
                    el.textContent = translated;
                }
            }
        });

        // 2. 인풋 요소 등의 플레이스홀더 번역
        root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                el.setAttribute('placeholder', this.t(key));
            }
        });

        // 3. 요소의 툴팁 도움말(title) 번역
        root.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                el.setAttribute('title', this.t(key));
            }
        });
    },

    /**
     * 동적 다국어 셀렉터 UI 구성
     * @param {string} containerSelector - 셀렉터가 삽입될 부모 엘리먼트 선택자
     */
    renderLanguageSelector(containerSelector) {
        const container = document.querySelector(containerSelector);
        if (!container) return;

        // 기존 언어 선택기 제거 후 새로 그림
        container.querySelectorAll('.i18n-selector-wrapper').forEach(el => el.remove());

        const wrapper = document.createElement('div');
        wrapper.className = 'i18n-selector-wrapper';
        wrapper.style.display = 'inline-block';
        wrapper.style.marginLeft = '10px';

        const select = document.createElement('select');
        select.className = 'form-select i18n-language-select';
        select.style.padding = '4px 8px';
        select.style.fontSize = '12px';
        select.style.cursor = 'pointer';
        select.style.borderRadius = '4px';
        select.style.border = '1px solid var(--border-color, #dbdbdb)';
        select.style.backgroundColor = 'var(--bg-card, #ffffff)';
        select.style.color = 'var(--text-main, #333333)';

        this.availableLanguages.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang.code;
            opt.textContent = lang.name;
            if (lang.code === this.currentLang) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        select.addEventListener('change', async (e) => {
            const selectedLang = e.target.value;
            if (selectedLang !== this.currentLang) {
                // 로더 표시 등 사용자 차단 필요 시 처리 가능
                await this.loadLanguagePack(selectedLang);
                this.translateDOM();
                
                // 설정 화면의 다른 선택기 상태 동기화
                document.querySelectorAll('.i18n-language-select').forEach(sel => {
                    if (sel !== select) sel.value = selectedLang;
                });

                // 언어 변경 후 커스텀 이벤트 전파 (필요시 리렌더링 바인딩용)
                window.dispatchEvent(new CustomEvent('bookoasis_language_changed', { detail: selectedLang }));
            }
        });

        wrapper.appendChild(select);
        container.appendChild(wrapper);
    }
};

window.i18n = i18n;

