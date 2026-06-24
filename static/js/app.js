document.addEventListener('DOMContentLoaded', () => {
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
    
    // file:// 프로토콜 방지 방어 코드
    if (window.location.protocol === 'file:') {
        alert('경고: 이 프로그램은 백엔드 서버(FastAPI)와 연동되어야 정상 작동합니다.\n\n브라우저 주소창에 http://127.0.0.1:8000 을 입력하여 접속해 주세요.');
        apiStatusBanner.className = 'glass-card api-alert';
        apiStatusBanner.querySelector('.alert-icon i').className = 'fa-solid fa-triangle-exclamation';
        apiStatusBanner.querySelector('h4').textContent = '로컬 파일 직접 실행 제한';
        apiStatusBanner.querySelector('p').innerHTML = '현재 로컬 html 파일을 직접 열었습니다. 서버와의 통신이 불가하므로, 반드시 주소창에 <a href="http://127.0.0.1:8000" style="color:#00f2fe; text-decoration:underline;">http://127.0.0.1:8000</a> 을 직접 입력해 접속하십시오.';
        return;
    }

    const chartLoading = document.getElementById('chart-loading');
    const chartPlaceholder = document.getElementById('chart-placeholder');
    const summaryCardsContainer = document.getElementById('summary-cards-container');
    const reportSection = document.getElementById('report-section');
    const reportModelDesc = document.getElementById('report-model-desc');
    const reportInsights = document.getElementById('report-insights');

    // Chart Helper 인스턴스 생성
    const chartHelper = new TrendChartHelper('trend-chart');

    // 2. 초기 기본값 설정 (조회 기간: 과거 1년 ~ 오늘)
    const today = new Date();
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(today.getFullYear() - 1);

    endDateInput.value = formatDate(today);
    startDateInput.value = formatDate(oneYearAgo);

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

        // 세부 필터 파싱
        const device = document.querySelector('input[name="device"]:checked').value;
        const gender = document.querySelector('input[name="gender"]:checked').value;
        const ages = Array.from(document.querySelectorAll('input[name="ages"]:checked')).map(el => el.value);

        if (device) payload.device = device;
        if (gender) payload.gender = gender;
        if (ages.length > 0) payload.ages = ages;

        try {
            const response = await fetch('/api/predict', {
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
            
            // 네이버 API 연동 상태 배너 업데이트 (정상 연결 확인)
            apiStatusBanner.className = 'glass-card api-alert api-ok';
            apiStatusBanner.querySelector('.alert-icon i').className = 'fa-solid fa-circle-check';
            apiStatusBanner.querySelector('h4').textContent = '네이버 API 연동 성공';
            apiStatusBanner.querySelector('p').textContent = '데이터가 안정적으로 연결되어 시계열 예측 처리가 완수되었습니다.';

            // 1. 차트 렌더링
            chartHelper.renderChart(data.results);

            // 2. 요약 카드 동적 렌더링
            renderSummaryCards(data.results, payload.timeUnit);

            // 3. 리포트 본문 구성
            renderDetailedReport(data.results, payload.timeUnit);

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
});
