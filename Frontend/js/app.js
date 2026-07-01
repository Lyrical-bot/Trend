const API_BASE_URL = 'https://trend-fpe5hmgxazgtegg2.koreacentral-01.azurewebsites.net';

document.addEventListener('DOMContentLoaded', () => {
    // 새로고침 시 무조건 화면 맨 위 상단을 보여주도록 브라우저 스크롤 강제 복원 비활성화 및 스크롤 탑 이동
    if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
    }
    window.scrollTo(0, 0);

    // 1. DOM Elements
    const forecastForm = document.getElementById('forecast-form');
    const keywordGroupsContainer = document.getElementById('keyword-groups-container');
    const btnAddGroup = document.getElementById('btn-add-group');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const filterAccordionToggle = document.getElementById('filter-accordion-toggle');
    const filterBody = document.getElementById('filter-body');
    const accordion = filterAccordionToggle.closest('.accordion');
    const apiStatusBanner = document.getElementById('api-status-banner');

    // file:// 프로토콜 방지 방어 코드 (알림만 표시하고 실행은 차단하지 않도록 수정)
    if (window.location.protocol === 'file:') {
        apiStatusBanner.className = 'glass-card api-alert';
        apiStatusBanner.querySelector('.alert-icon i').className = 'fa-solid fa-triangle-exclamation';
        apiStatusBanner.querySelector('h4').textContent = '로컬 파일 직접 실행 모드';
        apiStatusBanner.querySelector('p').innerHTML = '현재 로컬 html 파일을 직접 열었습니다. API 서버(127.0.0.1:8000)가 정상 구동 중이면 원격 데이터 분석이 가능합니다.';
    }

    // 검색 및 기상청 데이터 상태 캐싱용 전역 객체 바인딩
    window.currentPredictResults = null;
    window.currentWeatherData = null;

    const chartLoading = document.getElementById('chart-loading');
    const chartPlaceholder = document.getElementById('chart-placeholder');
    const summaryCardsContainer = document.getElementById('summary-cards-container');

    // 모든 날짜 선택 상자(Input Box) 클릭 시 달력 피커 자동 팝업
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        input.style.cursor = 'pointer';
        input.addEventListener('click', function() {
            if (typeof this.showPicker === 'function') {
                try {
                    this.showPicker();
                } catch (e) {
                    console.warn("showPicker failed:", e);
                }
            }
        });
    });

    // 기상청 체크박스 옵션 리스너
    const chkTemp = document.getElementById('chk-weather-temp');
    const chkRain = document.getElementById('chk-weather-rain');
    
    function updateChartWithWeather() {
        if (!window.currentPredictResults || !window.trendChartHelper) return;
        const showTemp = chkTemp ? chkTemp.checked : false;
        const showRain = chkRain ? chkRain.checked : false;
        window.trendChartHelper.renderChart(
            window.currentPredictResults,
            false,
            window.currentWeatherData,
            showTemp,
            showRain
        );
    }

    if (chkTemp) chkTemp.addEventListener('change', updateChartWithWeather);
    if (chkRain) chkRain.addEventListener('change', updateChartWithWeather);

    // 줌 인/아웃 버튼 이벤트 리스너 바인딩
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => {
            if (window.trendChartHelper) {
                window.trendChartHelper.zoom('in');
            }
        });
    }
    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => {
            if (window.trendChartHelper) {
                window.trendChartHelper.zoom('out');
            }
        });
    }

    // 백테스트 검증 차트 줌 인/아웃 버튼 이벤트 리스너 바인딩
    const btnBtZoomIn = document.getElementById('btn-bt-zoom-in');
    const btnBtZoomOut = document.getElementById('btn-bt-zoom-out');
    if (btnBtZoomIn) {
        btnBtZoomIn.addEventListener('click', () => {
            if (window.backtestChartHelper) {
                window.backtestChartHelper.zoom('in');
            }
        });
    }
    if (btnBtZoomOut) {
        btnBtZoomOut.addEventListener('click', () => {
            if (window.backtestChartHelper) {
                window.backtestChartHelper.zoom('out');
            }
        });
    }
    const reportSection = document.getElementById('report-section');
    const reportModelDesc = document.getElementById('report-model-desc');
    const reportInsights = document.getElementById('report-insights');
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', handleAnalyze);
    }

    // Chart Helper 인스턴스 생성 (상단: 예측, 하단: 백테스트)
    window.trendChartHelper = new TrendChartHelper('trend-chart');
    window.backtestChartHelper = new TrendChartHelper('backtest-chart');

    // 페이지 로드 시 랭킹 및 Weak Signal 자동 로드
    fetchVelocityRanking();

    // 2. 초기 기본값 설정 (조회 기간: 과거 10년 ~ 오늘)
    const today = new Date();
    const tenYearsAgo = new Date();
    tenYearsAgo.setFullYear(today.getFullYear() - 10);

    endDateInput.value = formatDate(today);
    startDateInput.value = formatDate(tenYearsAgo);

    // 3. 필터 아코디언 토글 이벤트
    filterAccordionToggle.addEventListener('click', () => {
        const isOpen = accordion.classList.contains('open');
        if (isOpen) {
            accordion.classList.remove('open');
            filterBody.style.display = 'none';
        } else {
            accordion.classList.add('open');
            filterBody.style.display = 'block';
        }
    });

    // 4. 키워드 그룹 추가/삭제 이벤트 관리
    let groupIndex = 2; // 초기 index.html에 0, 1이 들어 있으므로 다음은 2

    btnAddGroup.addEventListener('click', () => {
        const currentGroups = keywordGroupsContainer.querySelectorAll('.keyword-group-item');
        if (currentGroups.length >= 3) {
            alert('키워드 그룹은 최대 3개까지만 비교할 수 있습니다.');
            return;
        }

        const newGroup = document.createElement('div');
        newGroup.className = 'keyword-group-item glass-input-group';
        newGroup.dataset.index = groupIndex;
        newGroup.innerHTML = `
            <div class="group-header">
                <span class="group-num">그룹 ${currentGroups.length + 1}</span>
                <button type="button" class="btn-remove-group"><i class="fa-solid fa-trash"></i></button>
            </div>
            <input type="text" class="input-group-name" placeholder="그룹 명" required>
            <input type="text" class="input-keywords" placeholder="쉼표로 키워드 구분" required>
        `;
        keywordGroupsContainer.appendChild(newGroup);
        groupIndex++;
        updateGroupNumbers();
    });

    keywordGroupsContainer.addEventListener('click', (e) => {
        if (e.target.closest('.btn-remove-group')) {
            const groupItem = e.target.closest('.keyword-group-item');
            groupItem.remove();
            updateGroupNumbers();
        }
    });

    function updateGroupNumbers() {
        const groups = keywordGroupsContainer.querySelectorAll('.keyword-group-item');
        groups.forEach((group, idx) => {
            group.querySelector('.group-num').textContent = `그룹 ${idx + 1}`;
            const removeBtn = group.querySelector('.btn-remove-group');
            if (groups.length === 1) {
                removeBtn.style.display = 'none';
            } else {
                removeBtn.style.display = 'block';
            }
        });
    }

    // 5. 폼 서브밋 & 예측 수행
    forecastForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI 상태 초기화
        chartPlaceholder.style.display = 'none';
        chartLoading.style.display = 'flex';
        summaryCardsContainer.style.display = 'none';
        reportSection.style.display = 'none';

        // 백테스트 차트 및 관련 캡션 초기화
        const btPlaceholder = document.getElementById('backtest-placeholder');
        const btChartDiv = document.getElementById('backtest-chart');
        const btCaption = document.getElementById('backtest-chart-caption');
        const btScrollbarContainer = document.getElementById('backtest-chart-scrollbar-container');
        if (btPlaceholder) btPlaceholder.style.display = 'flex';
        if (btChartDiv) {
            btChartDiv.style.opacity = '1';
            btChartDiv.innerHTML = '';
        }
        if (btCaption) btCaption.style.display = 'none';
        if (btScrollbarContainer) btScrollbarContainer.style.display = 'none';

        const btTitle = document.getElementById('backtest-chart-title');
        if (btTitle) btTitle.textContent = "모델 정확도 검증 (과거 15일 백테스트)";

        // 예측 차트 캡션 및 스크롤바 숨기기
        const trendCaption = document.getElementById('trend-chart-caption');
        const trendScrollbarContainer = document.getElementById('trend-chart-scrollbar-container');
        if (trendCaption) trendCaption.style.display = 'none';
        if (trendScrollbarContainer) trendScrollbarContainer.style.display = 'none';

        // 데이터 파싱
        const payload = {
            startDate: startDateInput.value,
            endDate: endDateInput.value,
            timeUnit: document.getElementById('time-unit').value,
            forecastSteps: parseInt(document.getElementById('forecast-steps').value),
            keywordGroups: []
        };

        // 키워드 그룹 파싱
        const groupItems = keywordGroupsContainer.querySelectorAll('.keyword-group-item');
        groupItems.forEach(item => {
            const groupName = item.querySelector('.input-group-name').value.trim();
            const rawKeywords = item.querySelector('.input-keywords').value;
            const keywords = rawKeywords.split(',')
                .map(kw => kw.trim())
                .filter(kw => kw.length > 0);

            if (groupName && keywords.length > 0) {
                payload.keywordGroups.push({ groupName, keywords });
            }
        });

        // 로딩 메시지에 사용자 입력 키워드 동적 매핑
        const loadingMsg = document.getElementById('loading-msg');
        if (loadingMsg && payload.keywordGroups.length > 0) {
            const firstGroup = payload.keywordGroups[0];
            loadingMsg.innerHTML = `<strong>${firstGroup.groupName}</strong> 과거 데이터 수집 및 머신러닝 예측을 수행하는 중...`;
        }

        // 세부 필터 파싱
        const device = document.querySelector('input[name="device"]:checked').value;
        const gender = document.querySelector('input[name="gender"]:checked').value;
        const ages = Array.from(document.querySelectorAll('input[name="ages"]:checked')).map(el => el.value);

        if (device) payload.device = device;
        if (gender) payload.gender = gender;
        if (ages.length > 0) payload.ages = ages;

        // 기상 변수 반영 옵션 파싱 (차트 영역 상단의 기온/강수량 체크박스 연동)
        const useTemp = document.getElementById('chk-weather-temp') ? document.getElementById('chk-weather-temp').checked : true;
        const useRain = document.getElementById('chk-weather-rain') ? document.getElementById('chk-weather-rain').checked : true;
        payload.use_temp = useTemp;
        payload.use_rain = useRain;

        try {
            const response = await fetch(`${API_BASE_URL}/api/predict`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '트렌드 분석 중 오류가 발생했습니다.');
            }

            // 성공 처리
            chartLoading.style.display = 'none';
            chartPlaceholder.style.display = 'none';

            // 네이버 API 연동 상태 배너 업데이트 (정상 연결 확인)
            apiStatusBanner.className = 'glass-card api-alert api-ok';
            apiStatusBanner.querySelector('.alert-icon i').className = 'fa-solid fa-circle-check';
            apiStatusBanner.querySelector('h4').textContent = '네이버 API 연동 성공';
            apiStatusBanner.querySelector('p').textContent = '데이터가 안정적으로 연결되어 시계열 예측 처리가 완수되었습니다.';

            // 기상청 데이터와 트렌드 결과 캐싱
            window.currentPredictResults = data.results;
            window.currentWeatherData = data.weather;

            // 1. 차트 렌더링 (기상청 오버레이 체크 여부 전달)
            const showTemp = chkTemp ? chkTemp.checked : false;
            const showRain = chkRain ? chkRain.checked : false;
            window.trendChartHelper.renderChart(data.results, false, data.weather, showTemp, showRain);

            // 미래 예측 차트 제목 업데이트
            const trendTitle = document.getElementById('trend-chart-title');
            if (trendTitle && payload.keywordGroups.length > 0) {
                const groupNames = payload.keywordGroups.map(g => g.groupName).join(', ');
                trendTitle.textContent = `미래 30일 트렌드 예측 시각화: [${groupNames}]`;
            }

            // 2. 요약 카드 동적 렌더링
            renderSummaryCards(data.results, payload.timeUnit);

            // 3. 리포트 본문 구성
            renderDetailedReport(data.results, payload.timeUnit);

            // 차트 영역으로 자동 스크롤 이동
            const trendSection = document.getElementById('trend-chart');
            if (trendSection) {
                trendSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

        } catch (err) {
            chartLoading.style.display = 'none';
            chartPlaceholder.style.display = 'flex';

            // API 에러 상태 배너 업데이트
            apiStatusBanner.className = 'glass-card api-alert';
            apiStatusBanner.querySelector('.alert-icon i').className = 'fa-solid fa-triangle-exclamation';
            apiStatusBanner.querySelector('h4').textContent = '분석 수행 실패';
            apiStatusBanner.querySelector('p').innerHTML = `오류 내용: <strong>${err.message}</strong><br>서버의 <code>.env</code> 파일에 네이버 API ID와 Secret이 잘 기입되었는지 확인해 주세요.`;

            alert(`에러 발생: ${err.message}`);
        }
    });

    // 6. 렌더링 서브 함수들
    function renderSummaryCards(results, timeUnit) {
        summaryCardsContainer.innerHTML = '';
        summaryCardsContainer.style.display = 'grid';

        const unitText = timeUnit === 'date' ? '일' : (timeUnit === 'week' ? '주' : '개월');

        results.forEach((group, index) => {
            const summary = group.summary;
            const card = document.createElement('div');
            card.className = `glass-card summary-card group-${index}`;

            // 트렌드 상태에 따른 뱃지 및 아이콘 결정
            let badgeClass = 'flat';
            let badgeIcon = 'fa-minus';
            if (summary.trendStatus.includes('상승')) {
                badgeClass = 'up';
                badgeIcon = 'fa-arrow-trend-up';
            } else if (summary.trendStatus.includes('하락')) {
                badgeClass = 'down';
                badgeIcon = 'fa-arrow-trend-down';
            }

            card.innerHTML = `
                <div class="card-title">${group.title}</div>
                <div class="card-keywords">${group.keywords.join(', ')}</div>
                <div class="metric-row">
                    <div class="metric-val">${summary.lastForecastValue}%</div>
                    <div class="trend-badge ${badgeClass}">
                        <i class="fa-solid ${badgeIcon}"></i> ${summary.trendStatus}
                    </div>
                </div>
                <div class="card-info">
                    <span>최고점 예상 시점: <strong>${summary.maxDate}</strong> (${summary.maxRatio}%)</span>
                </div>
            `;
            summaryCardsContainer.appendChild(card);
        });
    }

    function renderDetailedReport(results, timeUnit) {
        reportSection.style.display = 'block';

        // 1. 모델 설명 업데이트
        // 어떤 모델이 사용되었는지 목록을 파싱
        const models = results.map(g => `${g.title} (${g.summary.modelUsed})`);
        reportModelDesc.innerHTML = `
            각 키워드 그룹별 특성에 맞춰 최적의 예측 모델이 매핑되었습니다.<br>
            <strong>적용 결과:</strong><br>
            ${models.map(m => `• ${m}`).join('<br>')}<br><br>
            데이터 관측수가 충분한 경우 Holt-Winters 모델을 통해 계절적 패턴을 감지하고 추세를 추정하며, 불규칙하거나 데이터가 적을 경우에는 추세 중심의 다항 회귀모델을 적용합니다.
        `;

        // 2. 인사이트 분석 생성
        reportInsights.innerHTML = '';
        const unitText = timeUnit === 'date' ? '일' : (timeUnit === 'week' ? '주' : '달');

        results.forEach(group => {
            const summary = group.summary;
            const li = document.createElement('li');

            let insightMsg = '';
            if (summary.trendStatus.includes('급격한 상승세')) {
                insightMsg = `<strong>[${group.title}]</strong> 키워드는 최근 매우 높은 관심도를 유지하고 있으며, 향후에도 강력한 트렌드 확장이 예상되어 즉각적인 마케팅/콘텐츠 타겟팅에 적합합니다.`;
            } else if (summary.trendStatus.includes('완만한 상승세')) {
                insightMsg = `<strong>[${group.title}]</strong> 키워드는 꾸준하게 관심도가 상승하는 안정적인 트렌드 카테고리입니다. 중장기적인 성장이 이어질 것입니다.`;
            } else if (summary.trendStatus.includes('급격한 하락세')) {
                insightMsg = `<strong>[${group.title}]</strong> 키워드는 현재 유행 사이클의 후반부에 도달한 것으로 보이며, 관심도가 급격히 식어가고 있어 리소스 투입의 축소를 고려해야 합니다.`;
            } else if (summary.trendStatus.includes('완만한 하락세')) {
                insightMsg = `<strong>[${group.title}]</strong> 키워드는 서서히 관심도가 감소하는 소강 상태에 진입하고 있어, 트렌드 다변화 대책이 요구됩니다.`;
            } else {
                insightMsg = `<strong>[${group.title}]</strong> 키워드는 현재 검색 볼륨 변동이 크지 않은 정체/안정기 상태이며, 급격한 이벤트가 없는 한 현재 트렌드를 유지할 전망입니다.`;
            }

            // 최고점 시점 해석 추가
            const maxDateObj = new Date(summary.maxDate);
            const todayObj = new Date();
            const diffDays = Math.ceil((maxDateObj - todayObj) / (1000 * 60 * 60 * 24));

            if (diffDays > 0) {
                insightMsg += ` 향후 대략 <strong>${diffDays}일 뒤</strong>인 <strong>${summary.maxDate}</strong> 경에 최대 트렌드 비율(${summary.maxRatio}%)에 도달할 것으로 계산되어 해당 시점을 겨냥한 프로모션 기획이 권장됩니다.`;
            } else {
                insightMsg += ` 과거 관측 기간 내인 <strong>${summary.maxDate}</strong>에 최고점(${summary.maxRatio}%)을 이미 경과한 상태로 판단됩니다.`;
            }

            li.innerHTML = insightMsg;
            reportInsights.appendChild(li);
        });
    }

    // 7. 유틸리티 함수: YYYY-MM-DD 포맷
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    // [추가] 가속도 랭킹 기간 기본값 설정 (최근 3일)
    const velEndDate = new Date();
    const velStartDate = new Date();
    velStartDate.setDate(velEndDate.getDate() - 2);

    const velStartInput = document.getElementById('vel-start-date');
    const velEndInput = document.getElementById('vel-end-date');
    if (velStartInput && velEndInput) {
        velStartInput.value = formatDate(velStartDate);
        velEndInput.value = formatDate(velEndDate);
    }

    // [추가] Weak Signal 엔진 기준일 기본값 설정 (오늘)
    const weakStartInput = document.getElementById('weak-start-date');
    const weakEndInput = document.getElementById('weak-end-date');
    if (weakStartInput && weakEndInput) {
        const weakStartDate = new Date();
        weakStartDate.setDate(weakStartDate.getDate() - 2); // 기본 3일 기간처럼 보이게
        weakStartInput.value = formatDate(weakStartDate);
        weakEndInput.value = formatDate(new Date());
    }

    // [추가] 가속도 랭킹 렌더링 호출
    if (typeof window.fetchVelocityRanking === 'function') {
        window.fetchVelocityRanking();
    }

    // [추가] Weak Signal 예측 엔진 호출
    if (typeof window.fetchWeakSignals === 'function') {
        window.fetchWeakSignals();
    }
});

// 가속도 랭킹을 서버에서 불러와 화면에 그리는 전역 함수
window.fetchVelocityRanking = async function () {
    const tbody = document.getElementById('velocity-ranking-list');
    const velStartInput = document.getElementById('vel-start-date');
    const velEndInput = document.getElementById('vel-end-date');

    if (!tbody) return; // 모듈이 없으면 실행 안함

    let queryParams = '';
    if (velStartInput && velEndInput && velStartInput.value && velEndInput.value) {
        queryParams = `?start_date=${velStartInput.value}&end_date=${velEndInput.value}&use_live=false`;
    }

    tbody.innerHTML = `<tr>
        <td colspan="5" style="padding: 30px; color: var(--text-muted);">
            <div class="spinner" style="width:20px;height:20px;display:inline-block;vertical-align:middle;margin-right:10px;"></div>
            데이터를 불러오는 중...
        </td>
    </tr>`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/velocity-ranking${queryParams}`);
        const result = await response.json();

        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="5" style="padding: 30px; color: var(--text-muted);">
                <i class="fa-solid fa-circle-exclamation"></i> ${result.detail || '가속도 랭킹을 불러올 수 없습니다.'}
            </td></tr>`;
            return;
        }

        const data = result.data;
        if (!data || data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="padding: 30px; color: var(--text-muted);">데이터가 없습니다.</td></tr>`;
            return;
        }

        let html = '';
        data.forEach((row, index) => {
            let symbol = '';
            let color = '';
            if (row.velocity_score > 50) {
                symbol = '🚀🚀 +'; color = '#ef4444'; // 빨간색 강조
            } else if (row.velocity_score > 0) {
                symbol = '🚀 +'; color = '#ef4444';
            } else {
                symbol = '📉 '; color = '#3b82f6'; // 파란색
            }

            html += `
                <tr onclick="window.analyzeKeyword('${row.keyword}')" style="border-bottom: 1px solid var(--border-light); transition: background-color 0.2s; cursor: pointer;" onmouseover="this.style.backgroundColor='rgba(139, 92, 246, 0.1)'" onmouseout="this.style.backgroundColor='transparent'">
                    <td style="padding: 12px; font-weight: 700; color: var(--text-main);">${index + 1}</td>
                    <td style="padding: 12px; text-align: left; font-weight: 500;">${row.keyword}</td>
                    <td style="padding: 12px; color: var(--text-muted);">${row.avg_prev_7.toLocaleString()}건</td>
                    <td style="padding: 12px; font-weight: 600;">${row.avg_recent_3.toLocaleString()}건</td>
                    <td style="padding: 12px; font-weight: 700; color: ${color};">${symbol}${row.velocity_score}%</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;

    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" style="padding: 30px; color: var(--text-muted);">서버와 연결할 수 없습니다.</td></tr>`;
    }
};

// Weak Signal 감지 엔진 데이터를 불러오는 전역 함수
window.fetchWeakSignals = async function () {
    const tbody = document.getElementById('weak-signal-list');
    const weakEndInput = document.getElementById('weak-end-date');

    if (!tbody) return;

    let queryParams = '';
    if (weakEndInput && weakEndInput.value) {
        queryParams = `?target_date=${weakEndInput.value}`;
    }

    tbody.innerHTML = `<tr>
        <td colspan="10" style="padding: 30px; color: var(--text-muted);">
            <div class="spinner" style="width:20px;height:20px;display:inline-block;vertical-align:middle;margin-right:10px;"></div>
            AI 모델이 피처를 분석하고 있습니다...
        </td>
    </tr>`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/weak-signals${queryParams}`);
        const result = await response.json();

        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="10" style="padding: 30px; color: var(--text-muted);">
                <i class="fa-solid fa-circle-exclamation"></i> ${result.detail || '데이터를 불러올 수 없습니다.'}
            </td></tr>`;
            return;
        }

        const data = result.data;
        if (!data || data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" style="padding: 30px; color: var(--text-muted);">데이터가 없습니다.</td></tr>`;
            return;
        }

        // 전역 변수에 데이터 저장 (페이지네이션 용)
        window.weakSignalData = result.data;
        window.currentWeakSignalPage = 1;

        // 첫 페이지 렌더링
        window.renderWeakSignalPage(1);

    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="10" style="padding: 30px; color: var(--text-muted);">서버와 연결할 수 없습니다.</td></tr>`;
    }
};

// 전역 변수
window.weakSignalData = [];
window.currentWeakSignalPage = 1;
const WEAK_SIGNAL_PER_PAGE = 20;

// 페이지네이션 렌더링 함수
window.renderWeakSignalPage = function (page) {
    const tbody = document.getElementById('weak-signal-list');
    const paginationContainer = document.getElementById('weak-signal-pagination');
    if (!tbody || !window.weakSignalData) return;

    const data = window.weakSignalData;
    const totalPages = Math.ceil(data.length / WEAK_SIGNAL_PER_PAGE);

    // 페이지 범위 보정
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;
    window.currentWeakSignalPage = page;

    // 현재 페이지 데이터 자르기
    const startIndex = (page - 1) * WEAK_SIGNAL_PER_PAGE;
    const endIndex = startIndex + WEAK_SIGNAL_PER_PAGE;
    const pageData = data.slice(startIndex, endIndex);

    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="padding: 30px; color: var(--text-muted);">데이터가 없습니다.</td></tr>`;
        if (paginationContainer) paginationContainer.innerHTML = '';
        return;
    }

    let html = '';
    pageData.forEach((row, idx) => {
        const actualIndex = startIndex + idx;

        // 시그널 등급 뱃지 색상
        let badgeStyle = 'background: #374151; color: #d1d5db;'; // IGNORE (Gray)
        if (row.signal_level === 'VERY HIGH') badgeStyle = 'background: #ef4444; color: white; box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);';
        else if (row.signal_level === 'HIGH') badgeStyle = 'background: #f97316; color: white;';
        else if (row.signal_level === 'MEDIUM') badgeStyle = 'background: #10b981; color: white;';
        else if (row.signal_level === 'LOW') badgeStyle = 'background: #6b7280; color: white;';

        html += `
            <tr onclick="window.analyzeKeyword('${row.keyword}')" style="border-bottom: 1px solid var(--border-light); transition: background-color 0.2s; cursor: pointer;" onmouseover="this.style.backgroundColor='rgba(139, 92, 246, 0.1)'" onmouseout="this.style.backgroundColor='transparent'">
                <td style="padding: 12px; font-weight: 700; color: var(--text-main);">${actualIndex + 1}</td>
                <td style="padding: 12px; text-align: left; font-weight: 700;">${row.keyword}</td>
                <td style="padding: 12px; font-weight: 800; font-size: 1.1rem; color: #8b5cf6;">${row.trend_score}</td>
                <td style="padding: 12px;">
                    <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; ${badgeStyle}">
                        ${row.signal_level}
                    </span>
                </td>
                <td style="padding: 12px; color: var(--text-muted);">${row.burst_ratio}배<br><span style="font-size:0.7rem; color: #8b5cf6;">(${row.burst_score}점)</span></td>
                <td style="padding: 12px; color: var(--text-muted);">${row.persistence_score}</td>
                <td style="padding: 12px; color: var(--text-muted);">${row.acceleration_score}</td>
                <td style="padding: 12px; color: var(--text-muted);">${row.stability_score}</td>
                <td style="padding: 12px; color: var(--text-muted);">${row.volume_score}</td>
                <td style="padding: 12px; font-weight: 600;">${row.growth_rate > 0 ? '+' : ''}${Math.round(row.growth_rate * 100)}%</td>
            </tr>
        `;
    });
    tbody.innerHTML = html;

    // 페이지네이션 버튼 생성
    if (paginationContainer && totalPages > 1) {
        let paginationHtml = `<div style="display: flex; justify-content: center; gap: 8px; margin-top: 16px;">`;

        // 이전 버튼
        if (page > 1) {
            paginationHtml += `<button class="btn-secondary btn-sm" onclick="window.renderWeakSignalPage(${page - 1})"><i class="fa-solid fa-chevron-left"></i></button>`;
        }

        // 페이지 번호 버튼 (최대 10개 표시 등 로직 추가 가능하나 전체 출력)
        let startPage = Math.max(1, page - 4);
        let endPage = Math.min(totalPages, startPage + 9);
        if (endPage - startPage < 9) {
            startPage = Math.max(1, endPage - 9);
        }

        for (let i = startPage; i <= endPage; i++) {
            if (i === page) {
                paginationHtml += `<button class="btn-primary btn-sm" style="background: #8b5cf6; border: none;">${i}</button>`;
            } else {
                paginationHtml += `<button class="btn-secondary btn-sm" onclick="window.renderWeakSignalPage(${i})">${i}</button>`;
            }
        }

        // 다음 버튼
        if (page < totalPages) {
            paginationHtml += `<button class="btn-secondary btn-sm" onclick="window.renderWeakSignalPage(${page + 1})"><i class="fa-solid fa-chevron-right"></i></button>`;
        }

        paginationHtml += `</div>`;
        paginationContainer.innerHTML = paginationHtml;
    } else if (paginationContainer) {
        paginationContainer.innerHTML = '';
    }
};

// Prophet 단일 키워드 예측 호출 및 백테스트 동시 실행
window.fetchSingleKeywordForecast = async function (keyword) {
    const chartContainer = document.querySelector('.chart-container');
    if (chartContainer) {
        chartContainer.scrollIntoView({ behavior: 'smooth' });
    }

    // 상단 예측 차트 DOM
    const placeholder = document.getElementById('chart-placeholder');
    const loading = document.getElementById('chart-loading');
    const loadingMsg = document.getElementById('loading-msg');
    const chartDiv = document.getElementById('trend-chart');

    // 하단 백테스트 차트 DOM
    const btPlaceholder = document.getElementById('backtest-placeholder');
    const btLoading = document.getElementById('backtest-loading');
    const btLoadingMsg = document.getElementById('backtest-loading-msg');
    const btChartDiv = document.getElementById('backtest-chart');

    const reportSection = document.getElementById('report-section');

    // 차트 제목 초기화
    const trendTitle = document.getElementById('trend-chart-title');
    const btTitle = document.getElementById('backtest-chart-title');
    if (trendTitle) trendTitle.textContent = "미래 30일 트렌드 예측 시각화";
    if (btTitle) btTitle.textContent = "모델 정확도 검증 (과거 15일 백테스트)";

    if (placeholder) placeholder.style.display = 'none';
    if (chartDiv) chartDiv.style.opacity = '0.3';
    
    // 로딩 시작 즉시 차트 날짜 밑에 검정색 검색 키워드 정보 노출
    const trendCaption = document.getElementById('trend-chart-caption');
    const btCaption = document.getElementById('backtest-chart-caption');
    if (trendCaption) {
        trendCaption.textContent = `검색한 키워드: ${keyword}`;
        trendCaption.style.display = 'block';
    }
    if (btCaption) {
        btCaption.textContent = `검색한 키워드: ${keyword}`;
        btCaption.style.display = 'block';
    }

    if (loading) {
        loading.style.display = 'flex';
        if (loadingMsg) loadingMsg.innerHTML = `<strong>${keyword}</strong> 과거 1년 데이터 수집 및 미래 30일 예측 수행 중...`;
    }

    if (btPlaceholder) btPlaceholder.style.display = 'none';
    if (btChartDiv) btChartDiv.style.opacity = '0.3';
    if (btLoading) {
        btLoading.style.display = 'flex';
        if (btLoadingMsg) btLoadingMsg.innerHTML = `<strong>${keyword}</strong> 1년치 과거 데이터 분할 백테스트 수행 중...`;
    }

    // 기상 변수 반영 옵션 파싱 (차트 영역 상단의 기온/강수량 체크박스 연동)
    const useTemp = document.getElementById('chk-weather-temp') ? document.getElementById('chk-weather-temp').checked : true;
    const useRain = document.getElementById('chk-weather-rain') ? document.getElementById('chk-weather-rain').checked : true;

    try {
        // 두 개의 API 병렬 호출
        const [predictResponse, evaluateResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/api/predict-keyword`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword: keyword, forecastSteps: 30, use_temp: useTemp, use_rain: useRain })
            }),
            fetch(`${API_BASE_URL}/api/evaluate-keyword`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword: keyword, use_temp: useTemp, use_rain: useRain })
            })
        ]);

        const predictResult = await predictResponse.json();
        const evaluateResult = await evaluateResponse.json();

        // 1. 예측 차트 렌더링
        if (loading) loading.style.display = 'none';
        if (chartDiv) chartDiv.style.opacity = '1';

        if (predictResponse.ok && window.trendChartHelper) {
            const formattedResults = [{
                title: predictResult.keyword,
                keywords: [predictResult.keyword],
                data: predictResult.data,
                signals: predictResult.signals || []
            }];
            // 캐싱 등록
            window.currentPredictResults = formattedResults;
            window.currentWeatherData = predictResult.weather;

            const showTemp = document.getElementById('chk-weather-temp') ? document.getElementById('chk-weather-temp').checked : false;
            const showRain = document.getElementById('chk-weather-rain') ? document.getElementById('chk-weather-rain').checked : false;

            window.trendChartHelper.renderChart(formattedResults, false, predictResult.weather, showTemp, showRain);

            // 미래 예측 차트 제목 업데이트
            const trendTitle = document.getElementById('trend-chart-title');
            if (trendTitle) {
                trendTitle.textContent = `미래 30일 트렌드 예측 시각화: [${keyword}]`;
            }
        } else {
            alert(`예측 실패: ${predictResult.detail || predictResult.error || '알 수 없는 오류'}`);
            if (placeholder) placeholder.style.display = 'flex';
            const trendCaption = document.getElementById('trend-chart-caption');
            if (trendCaption) trendCaption.style.display = 'none';
        }

        // 2. 백테스트 차트 렌더링
        if (btLoading) btLoading.style.display = 'none';
        if (btChartDiv) btChartDiv.style.opacity = '1';

        if (evaluateResponse.ok && window.backtestChartHelper) {
            window.backtestChartHelper.renderChart([{
                title: evaluateResult.keyword,
                keywords: [evaluateResult.keyword],
                data: evaluateResult.data
            }], true);

            // 백테스트 차트 제목 업데이트
            const btTitle = document.getElementById('backtest-chart-title');
            if (btTitle) {
                btTitle.textContent = `모델 정확도 검증: [${keyword}] (과거 15일 백테스트)`;
            }
        } else {
            if (btPlaceholder) btPlaceholder.style.display = 'flex';
            const btCaption = document.getElementById('backtest-chart-caption');
            if (btCaption) btCaption.style.display = 'none';
        }

        // 3. 리포트 렌더링
        if (reportSection && predictResponse.ok && evaluateResponse.ok) {
            reportSection.style.display = 'block';
            document.getElementById('report-model-desc').innerHTML = `
                <strong style="color: #6b52ff;">${predictResult.summary.modelUsed}</strong> 알고리즘을 사용해 미래를 시뮬레이션하고 정확도를 함께 검증했습니다.<br>
                과거 ${evaluateResult.summary.trainDays}일 데이터로 패턴을 파악한 뒤 숨겨진 ${evaluateResult.summary.testDays}일 구간을 통해 실력(정확도 ${evaluateResult.summary.accuracy}%)을 측정했습니다.
            `;

            let insightsHtml = `
                <li><strong>예상 트렌드:</strong> <span class="highlight">${predictResult.summary.trendStatus}</span></li>
                <li><strong>최고점 예상:</strong> <span class="highlight">${predictResult.summary.maxDate}</span> (약 ${predictResult.summary.maxRatio}건)</li>
                <li><strong>모델 오차율 (MAPE):</strong> <span class="highlight" style="color:#ef4444">${evaluateResult.summary.mape}%</span> (정확도 <span style="color:#10b981;font-weight:bold;">${evaluateResult.summary.accuracy}%</span>)</li>
            `;
            if (Array.isArray(predictResult.signals) && predictResult.signals.length > 0) {
                const firstSignal = predictResult.signals[0];
                insightsHtml += `
                    <li><strong>조기 경보:</strong> <span class="highlight">${firstSignal.date}</span>에 ${firstSignal.label} (점수 ${firstSignal.score}, 당시 약 ${Math.round(firstSignal.volume).toLocaleString()}건)</li>
                `;
            }
            document.getElementById('report-insights').innerHTML = insightsHtml;
        }

        // 차트 영역으로 자동 스크롤 이동
        const trendSection = document.getElementById('trend-chart');
        if (trendSection) {
            trendSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

    } catch (error) {
        if (loading) loading.style.display = 'none';
        if (chartDiv) chartDiv.style.opacity = '1';
        if (btLoading) btLoading.style.display = 'none';
        if (btChartDiv) btChartDiv.style.opacity = '1';

        const trendCaption = document.getElementById('trend-chart-caption');
        const btCaption = document.getElementById('backtest-chart-caption');
        if (trendCaption) trendCaption.style.display = 'none';
        if (btCaption) btCaption.style.display = 'none';

        alert('서버와 통신하는 중 오류가 발생했습니다.');

        if (placeholder) placeholder.style.display = 'flex';
        if (btPlaceholder) btPlaceholder.style.display = 'flex';
    }
};

// 유튜브 SNS 트렌드 (MVP) 호출 및 렌더링
window.fetchSnsTrend = async function(keywordArg) {
    const inputEl = document.getElementById('sns-keyword-input');
    const keyword = keywordArg || (inputEl ? inputEl.value.trim() : '');
    
    if (!keyword) {
        alert('키워드를 입력해주세요.');
        return;
    }

    const loading = document.getElementById('sns-loading');
    const placeholder = document.getElementById('sns-placeholder');
    const chartDiv = document.getElementById('sns-chart');
    const metricsContainer = document.getElementById('sns-metrics-container');
    
    // 차트 제목 초기화
    const snsTitle = document.getElementById('sns-chart-title');
    if (snsTitle) {
        snsTitle.textContent = "유튜브 SNS 트렌드 4대 지표 추적 (MVP)";
    }

    if (placeholder) placeholder.style.display = 'none';
    if (chartDiv) chartDiv.style.display = 'none';
    if (metricsContainer) metricsContainer.style.display = 'none';
    
    // 로딩 시작 즉시 차트 날짜 밑에 검정색 검색 키워드 정보 노출
    const snsCaption = document.getElementById('sns-chart-caption');
    if (snsCaption) {
        snsCaption.textContent = `검색한 키워드: ${keyword}`;
        snsCaption.style.display = 'block';
    }

    if (loading) loading.style.display = 'flex';

    try {
        const response = await fetch(`${API_BASE_URL}/api/sns/keyword/${encodeURIComponent(keyword)}`);
        const result = await response.json();

        if (loading) loading.style.display = 'none';

        if (!response.ok) {
            alert(`분석 실패: ${result.detail || '알 수 없는 오류'}`);
            if (placeholder) placeholder.style.display = 'block';
            const snsCaption = document.getElementById('sns-chart-caption');
            if (snsCaption) snsCaption.style.display = 'none';
            return;
        }

        // 1. 4대 핵심 지표 렌더링
        if (metricsContainer) {
            metricsContainer.style.display = 'grid';
            
            const signals = result.signals || {};
            
            // 신규 진입 여부
            const isNew = signals.is_new_keyword;
            const elNew = document.getElementById('sns-metric-new');
            if (elNew) {
                elNew.textContent = isNew ? "최초 진입 🚀" : "기존 키워드";
                elNew.style.color = isNew ? "#10b981" : "#6b7280"; // 초록 / 회색
            }
            
            // Growth
            const elGrowth = document.getElementById('sns-metric-growth');
            if (elGrowth) {
                const g = signals.growth || 0;
                elGrowth.textContent = `${g > 0 ? '+' : ''}${g}%`;
                elGrowth.style.color = g > 50 ? "#ef4444" : (g > 0 ? "#f97316" : "#6b7280");
            }
            
            // Burst
            const elBurst = document.getElementById('sns-metric-burst');
            if (elBurst) {
                const b = signals.burst || 0;
                elBurst.textContent = `${b}배`;
                elBurst.style.color = b >= 3 ? "#ef4444" : "#f97316";
            }
            
            // Diversity (Unique Channels)
            const elDiv = document.getElementById('sns-metric-diversity');
            if (elDiv) {
                const unique_channels = signals.unique_channels || 0;
                const d = signals.channel_diversity || 0; // fallback if needed
                
                if (unique_channels > 0) {
                    elDiv.textContent = `${unique_channels}개 채널`;
                    elDiv.style.color = unique_channels >= 3 ? "#10b981" : (unique_channels >= 2 ? "#3b82f6" : "#ef4444");
                } else {
                    elDiv.textContent = `${d}`;
                    elDiv.style.color = d >= 0.8 ? "#10b981" : (d >= 0.5 ? "#3b82f6" : "#ef4444");
                }
            }
        }

        // 2. 교차 검증(블루오션 판별) API 호출
        const trendSynContainer = document.getElementById('trend-synthesis-container');
        const phaseEl = document.getElementById('trend-synthesis-phase');
        const msgEl = document.getElementById('trend-synthesis-msg');
        const badgeEl = document.getElementById('trend-synthesis-badge');
        
        if (trendSynContainer) {
            trendSynContainer.style.display = 'block';
            phaseEl.textContent = '상태 판별 중...';
            phaseEl.style.color = 'var(--text-primary)';
            msgEl.textContent = '네이버 대중 검색량과 유튜브 확산 지표를 교차 분석하고 있습니다.';
            badgeEl.textContent = '분석중';
            badgeEl.style.background = '#e5e7eb';
            badgeEl.style.color = '#6b7280';
            trendSynContainer.style.borderLeftColor = '#3b82f6';
            trendSynContainer.style.background = 'rgba(59, 130, 246, 0.05)';
            
            try {
                const synRes = await fetch(`${API_BASE_URL}/api/trend-synthesis?keyword=${encodeURIComponent(keyword)}`);
                if (synRes.ok) {
                    const synData = await synRes.json();
                    const phase = synData.phase;
                    
                    if (phase === 'GOLDEN_TIME') {
                        phaseEl.textContent = '🚀 MD 골든타임 (블루오션)';
                        phaseEl.style.color = '#10b981'; // Green
                        badgeEl.textContent = '적기';
                        badgeEl.style.background = '#10b981';
                        badgeEl.style.color = 'white';
                        trendSynContainer.style.borderLeftColor = '#10b981';
                        trendSynContainer.style.background = 'rgba(16, 185, 129, 0.05)';
                    } else if (phase === 'RED_OCEAN') {
                        phaseEl.textContent = '🔥 대중 확산기 (레드오션 진입)';
                        phaseEl.style.color = '#f97316'; // Orange (조심)
                        badgeEl.textContent = '조심';
                        badgeEl.style.background = '#f97316';
                        badgeEl.style.color = 'white';
                        trendSynContainer.style.borderLeftColor = '#f97316';
                        trendSynContainer.style.background = 'rgba(249, 115, 22, 0.05)';
                    } else if (phase === 'LATE_STAGE') {
                        phaseEl.textContent = '🥀 유행 끝물 (위험)';
                        phaseEl.style.color = '#ef4444'; // Red (위험)
                        badgeEl.textContent = '위험';
                        badgeEl.style.background = '#ef4444';
                        badgeEl.style.color = 'white';
                        trendSynContainer.style.borderLeftColor = '#ef4444';
                        trendSynContainer.style.background = 'rgba(239, 68, 68, 0.05)';
                    } else if (phase === 'NO_DATA') {
                        phaseEl.textContent = '⚠️ 유튜브 데이터 수집 대기';
                        phaseEl.style.color = '#6b7280'; // Gray
                        badgeEl.textContent = '대기';
                        badgeEl.style.background = '#6b7280';
                        badgeEl.style.color = 'white';
                        trendSynContainer.style.borderLeftColor = '#6b7280';
                        trendSynContainer.style.background = 'rgba(107, 114, 128, 0.05)';
                    } else {
                        phaseEl.textContent = '👀 관망 구간';
                        phaseEl.style.color = '#3b82f6'; // Blue
                        badgeEl.textContent = '관망';
                        badgeEl.style.background = '#3b82f6';
                        badgeEl.style.color = 'white';
                        trendSynContainer.style.borderLeftColor = '#3b82f6';
                        trendSynContainer.style.background = 'rgba(59, 130, 246, 0.05)';
                    }
                    
                    msgEl.textContent = synData.message;
                }
            } catch(e) {
                console.error("Trend Synthesis API Error:", e);
                phaseEl.textContent = '분석 실패';
                msgEl.textContent = '교차 분석 데이터를 불러오는 중 오류가 발생했습니다.';
            }
        }

        // 3. 타임라인 차트 렌더링
        if (chartDiv) {
            chartDiv.style.display = 'block';
            
            // 기존 차트 파괴 (ApexCharts)
            if (window.snsApexChart) {
                window.snsApexChart.destroy();
            }

            const timeline = result.timeline || [];
            
            if (timeline.length === 0) {
                chartDiv.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted);">현재 타임라인 데이터가 없습니다. 유튜브 수집기를 가동해주세요.</div>`;
                return;
            }

            const seriesData = timeline.map(item => ({
                x: new Date(item.hour).getTime(),
                y: item.count
            }));

            const options = {
                series: [{
                    name: '언급량(영상 수)',
                    data: seriesData
                }],
                chart: {
                    type: 'area',
                    height: 300,
                    toolbar: { show: false },
                    fontFamily: 'Noto Sans KR, sans-serif'
                },
                colors: ['#ef4444'],
                fill: {
                    type: 'gradient',
                    gradient: {
                        shadeIntensity: 1,
                        opacityFrom: 0.7,
                        opacityTo: 0.1,
                        stops: [0, 100]
                    }
                },
                dataLabels: { enabled: false },
                stroke: { curve: 'smooth', width: 3 },
                xaxis: {
                    type: 'datetime',
                    labels: { style: { colors: '#9ca3af' } }
                },
                yaxis: {
                    labels: { style: { colors: '#9ca3af' } }
                },
                grid: {
                    borderColor: 'rgba(255,255,255,0.05)',
                    strokeDashArray: 4
                },
                theme: { mode: 'dark' }
            };

            window.snsApexChart = new ApexCharts(chartDiv, options);
            window.snsApexChart.render();

            // 유튜브 SNS 언급량 차트 제목 업데이트
            const snsTitle = document.getElementById('sns-chart-title');
            if (snsTitle) {
                snsTitle.textContent = `유튜브 SNS 트렌드 4대 지표 추적: [${keyword}]`;
            }

            // 유튜브 차트 영역으로 자동 스크롤 이동
            const snsSection = document.getElementById('sns-chart');
            if (snsSection) {
                snsSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

    } catch (error) {
        if (loading) loading.style.display = 'none';
        if (placeholder) placeholder.style.display = 'block';
        const snsCaption = document.getElementById('sns-chart-caption');
        if (snsCaption) snsCaption.style.display = 'none';
        alert('SNS 트렌드 분석 중 오류가 발생했습니다.');
    }
};

// [추가] Discovery Engine이 찾아낸 트렌드 키워드 자동 로드
window.fetchDiscoveredKeywords = async function() {
    const container = document.getElementById('sns-discovered-keywords');
    if (!container) return;
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/sns/discovered-keywords`);
        if (!res.ok) throw new Error('API Error');
        const keywords = await res.json();
        
        container.innerHTML = '';
        if (keywords.length === 0) {
            container.innerHTML = '<span style="font-size: 0.8rem; color: var(--text-muted);">아직 수집된 핫 트렌드가 없습니다. 수집기를 가동해주세요.</span>';
            return;
        }
        
        keywords.forEach(k => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.style.cssText = 'background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; border-radius: 20px; padding: 4px 12px; font-size: 0.85rem; cursor: pointer; transition: all 0.2s;';
            chip.innerHTML = `#${k.keyword} <span style="opacity: 0.6; font-size: 0.75rem; margin-left: 4px;">${k.mentions}</span>`;
            
            // 호버 효과
            chip.onmouseover = () => { chip.style.background = 'rgba(239, 68, 68, 0.2)'; };
            chip.onmouseout = () => { chip.style.background = 'rgba(239, 68, 68, 0.1)'; };
            
            // 클릭 시 검색창에 넣고 자동 분석!
            chip.onclick = () => {
                window.analyzeKeyword(k.keyword);
            };
            
            container.appendChild(chip);
        });
        
    } catch (e) {
        container.innerHTML = '<span style="font-size: 0.8rem; color: var(--text-muted);">트렌드를 불러오는 중 오류가 발생했습니다.</span>';
    }
};

// 페이지 로드 시 Discovery 키워드 가져오기
document.addEventListener('DOMContentLoaded', () => {
    window.fetchDiscoveredKeywords();
});

// 통합 검색 분석 오케스트레이터 함수 (유튜브 SNS + 네이버 트렌드 예측 동시 반영)
window.analyzeKeyword = function(keyword) {
    if (!keyword) {
        alert('분석할 키워드를 입력해주세요.');
        return;
    }

    // 1. 유튜브 SNS 입력필드 동기화
    const inputEl = document.getElementById('sns-keyword-input');
    if (inputEl) {
        inputEl.value = keyword;
    }

    // 2. 왼쪽 사이드바 그룹 1 입력필드 동기화 (사이드바와 일관성 유지)
    const firstGroup = document.querySelector('#keyword-groups-container .keyword-group-item[data-index="0"]');
    if (firstGroup) {
        const groupNameInput = firstGroup.querySelector('.input-group-name');
        const keywordsInput = firstGroup.querySelector('.input-keywords');
        if (groupNameInput) groupNameInput.value = keyword;
        if (keywordsInput) keywordsInput.value = keyword;
    }

    // 3. 유튜브 SNS 분석 및 네이버 예측 병렬 구동
    window.fetchSnsTrend(keyword);
    window.fetchSingleKeywordForecast(keyword);
};
