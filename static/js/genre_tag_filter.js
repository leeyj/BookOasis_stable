// genre_tag_filter.js – 장르 및 태그 플로팅 모달창 관리 모듈
import { state } from './state.js';

let genresData = [];
let tagsData = [];
let selectedGenres = new Set();
let selectedTags = new Set();
let currentTab = 'genres'; // 'genres' or 'tags'
let activeDrag = false;
let currentX = 0;
let currentY = 0;
let initialX = 0;
let initialY = 0;
let xOffset = 0;
let yOffset = 0;

export async function initFloatingFilter() {
    const modal = document.getElementById('floating-filter-modal');
    const header = document.getElementById('filter-modal-header');
    const btnClose = document.getElementById('btn-filter-close');
    const btnReset = document.getElementById('btn-filter-reset');
    const btnApply = document.getElementById('btn-filter-apply');
    const tabGenres = document.getElementById('tab-genres');
    const tabTags = document.getElementById('tab-tags');
    const searchInput = document.getElementById('filter-search-input');

    if (!modal) return;

    // 드래그 앤 드롭 바인딩
    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mouseup', dragEnd);
    document.addEventListener('mousemove', drag);

    // 버튼 이벤트 바인딩
    btnClose.addEventListener('click', toggleFilterModal);
    btnReset.addEventListener('click', resetAllFilters);
    btnApply.addEventListener('click', applyFilters);

    tabGenres.addEventListener('click', () => switchFilterTab('genres'));
    tabTags.addEventListener('click', () => switchFilterTab('tags'));
    searchInput.addEventListener('input', onFilterSearchChange);

    // 전역 함수 바인딩 (HTML onclick 바인딩 호환용)
    window.toggleFilterModal = toggleFilterModal;
}

// 모달 토글
export function toggleFilterModal() {
    const modal = document.getElementById('floating-filter-modal');
    if (!modal) return;
    
    if (modal.style.display === 'none') {
        modal.style.display = 'flex';
        // 데이터를 로드하지 않은 상태라면 로드
        if (genresData.length === 0 || tagsData.length === 0) {
            loadGenresAndTagsData();
        }
    } else {
        modal.style.display = 'none';
    }
}

// 장르 및 태그 데이터 로드
export async function loadGenresAndTagsData() {
    const libraryId = state.currentLibraryId === 'all' || state.currentLibraryId === 'home' || state.currentLibraryId === 'history' || state.currentLibraryId === 'favorite' ? 'all' : state.currentLibraryId;
    const dbType = state.currentLibraryType || 'general';

    try {
        const [genresRes, tagsRes] = await Promise.all([
            fetch(`/api/media/genres?type=${dbType}&library_id=${libraryId}`).then(res => res.json()),
            fetch(`/api/media/tags?type=${dbType}&library_id=${libraryId}`).then(res => res.json())
        ]);

        if (genresRes.success) genresData = genresRes.genres || [];
        if (tagsRes.success) tagsData = tagsRes.tags || [];

        renderChips();
        renderSelectedChips();
    } catch (err) {
        console.error("[Filter] 장르 및 태그 목록 로드 실패:", err);
    }
}

// 탭 스위치
function switchFilterTab(tabName) {
    currentTab = tabName;
    
    const tabGenres = document.getElementById('tab-genres');
    const tabTags = document.getElementById('tab-tags');
    
    if (tabName === 'genres') {
        tabGenres.classList.add('active');
        tabTags.classList.remove('active');
    } else {
        tabTags.classList.add('active');
        tabGenres.classList.remove('active');
    }
    
    // 검색창 초기화 및 칩 렌더링
    document.getElementById('filter-search-input').value = '';
    renderChips();
}

// 실시간 검색 매칭
function onFilterSearchChange() {
    renderChips();
}

// 칩 렌더링
function renderChips() {
    const wrapper = document.getElementById('filter-chips-wrapper');
    const searchVal = document.getElementById('filter-search-input').value.trim().toLowerCase();
    
    if (!wrapper) return;
    wrapper.innerHTML = '';

    const list = currentTab === 'genres' ? genresData : tagsData;
    const selectedSet = currentTab === 'genres' ? selectedGenres : selectedTags;

    // 검색어 매칭 필터링
    const filteredList = list.filter(item => item.toLowerCase().includes(searchVal));

    if (filteredList.length === 0) {
        wrapper.innerHTML = `<span style="font-size: 0.8rem; color: #64748b; margin: 1rem auto;">검색 결과가 없습니다.</span>`;
        return;
    }

    filteredList.forEach(item => {
        const chip = document.createElement('div');
        chip.className = `filter-chip-item ${selectedSet.has(item) ? 'active' : ''}`;
        chip.innerText = item;
        chip.addEventListener('click', () => {
            toggleChipSelection(item);
        });
        wrapper.appendChild(chip);
    });
}

// 칩 선택/해제 토글
function toggleChipSelection(item) {
    const selectedSet = currentTab === 'genres' ? selectedGenres : selectedTags;
    if (selectedSet.has(item)) {
        selectedSet.delete(item);
    } else {
        selectedSet.add(item);
    }
    renderChips();
    renderSelectedChips();
}

// 선택된 칩 레이아웃 업데이트
function renderSelectedChips() {
    const container = document.getElementById('selected-chips-container');
    if (!container) return;

    container.innerHTML = '';
    
    if (selectedGenres.size === 0 && selectedTags.size === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';

    selectedGenres.forEach(genre => {
        const chip = createSelectedChipElement('genres', genre);
        container.appendChild(chip);
    });

    selectedTags.forEach(tag => {
        const chip = createSelectedChipElement('tags', tag);
        container.appendChild(chip);
    });
}

function createSelectedChipElement(type, value) {
    const chip = document.createElement('div');
    chip.className = 'filter-chip-selected';
    chip.innerHTML = `<span>[${type === 'genres' ? '장르' : '태그'}] ${value}</span> <i class="fa-solid fa-xmark" style="font-size: 0.7rem;"></i>`;
    chip.addEventListener('click', () => {
        if (type === 'genres') {
            selectedGenres.delete(value);
        } else {
            selectedTags.delete(value);
        }
        renderChips();
        renderSelectedChips();
    });
    return chip;
}

// 필터 적용
export function applyFilters() {
    // 선택된 필터 값을 state 객체에 보관하여 도서 검색과 결합할 수 있도록 전달
    state.filterGenres = Array.from(selectedGenres);
    state.filterTags = Array.from(selectedTags);

    // 필터링 적용을 위해 기존의 도서 검색/렌더링 호출
    if (typeof window.filterBooks === 'function') {
        window.filterBooks();
    }
    
    // 모달 닫기
    toggleFilterModal();
}

// 필터 전체 초기화
export function resetAllFilters() {
    selectedGenres.clear();
    selectedTags.clear();
    state.filterGenres = [];
    state.filterTags = [];
    
    document.getElementById('filter-search-input').value = '';
    renderChips();
    renderSelectedChips();

    // 필터링 갱신 호출
    if (typeof window.filterBooks === 'function') {
        window.filterBooks();
    }
}

// 드래그 앤 드롭 자유 이동
function dragStart(e) {
    const modal = document.getElementById('floating-filter-modal');
    if (e.target.closest('.filter-modal-header-actions')) return; // 닫기/초기화 버튼 클릭 시 드래그 방지

    initialX = e.clientX - xOffset;
    initialY = e.clientY - yOffset;

    if (e.target === document.getElementById('filter-modal-header') || e.target.parentNode === document.getElementById('filter-modal-header')) {
        activeDrag = true;
    }
}

function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    activeDrag = false;
}

function drag(e) {
    if (activeDrag) {
        e.preventDefault();
        
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;

        xOffset = currentX;
        yOffset = currentY;

        setTranslate(currentX, currentY, document.getElementById('floating-filter-modal'));
    }
}

function setTranslate(xPos, yPos, el) {
    el.style.transform = "translate3d(" + xPos + "px, " + yPos + "px, 0)";
}

// 기존 사이드바 필터 토글 호환용 스텁 함수
export function updateSidebarFilterActiveStates() {}
