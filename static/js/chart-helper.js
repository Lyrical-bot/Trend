class TrendChartHelper {
    constructor(containerId) {
        this.containerId = containerId;
        this.chart = null;
        // 그룹별 고유 컬러 팔레트 (Mint, Purple, Coral)
        this.colors = ['#1abc9c', '#6b52ff', '#ef4444'];
        this.colorsFade = ['rgba(26, 188, 156, 0.25)', 'rgba(107, 82, 255, 0.25)', 'rgba(239, 68, 68, 0.25)'];
    }

    /**
     * 네이버 API 가공 데이터를 기반으로 차트를 그립니다.
     * results: [{ title, keywords, data: [{ period, ratio, isForecast, type }] }]
     */
    renderChart(results, isBacktest = false) {
        if (this.chart) {
            this.chart.destroy();
        }

        const series = [];
        const strokeDashArray = [];
        const strokeColors = [];
        const fillColors = [];
        const markerSizes = [];
        const signalAnnotations = [];
        
        let allPeriods = [];

        // 모든 날짜 목록 수집 및 정렬 (중복 제거)
        if (results.length > 0) {
            allPeriods = Array.from(new Set(results[0].data.map(item => item.period))).sort();
        }

        results.forEach((group, index) => {
            const color = this.colors[index % this.colors.length];
            const fadeColor = this.colorsFade[index % this.colorsFade.length];
            const signals = Array.isArray(group.signals) ? group.signals : [];
            const trainColor = '#6b7280';
            const actualColor = '#3b82f6';
            const forecastColor = '#1abc9c';
            const signalColor = '#ef4444';

            signals.forEach(signal => {
                const point = group.data.find(item => item.period === signal.date && !item.isForecast);
                if (!point) return;

                signalAnnotations.push({
                    x: signal.date,
                    y: point.ratio,
                    marker: {
                        size: 7,
                        fillColor: signalColor,
                        strokeColor: '#ffffff',
                        strokeWidth: 2,
                        radius: 2
                    },
                    label: {
                        borderColor: signalColor,
                        offsetY: 0,
                        style: {
                            color: '#ffffff',
                            background: signalColor,
                            fontSize: '11px',
                            fontWeight: 700
                        },
                        text: `${signal.label || '유행 전조'} ${signal.score || ''}점`
                    }
                });
            });

            if (isBacktest) {
                // 백테스트 모드: train(학습), actual(실제), predicted(예측) 3가지 라인
                // 1. 학습 데이터 (Train) - 실선
                const trainData = allPeriods.map(p => {
                    const item = group.data.find(d => d.period === p && d.type === 'train');
                    return item ? item.ratio : null;
                });
                
                // 2. 실제 데이터 (Actual Test) - 실선, 좀 더 진한/다른 색
                let lastTrainVal = null;
                const actualData = allPeriods.map(p => {
                    const item = group.data.find(d => d.period === p && d.type === 'actual');
                    if (item) return item.ratio;
                    
                    // 연결을 위해 train의 마지막 값 가져오기
                    const tItem = group.data.find(d => d.period === p && d.type === 'train');
                    if (tItem) lastTrainVal = tItem.ratio;
                    
                    // Train의 가장 마지막 요소와 Actual의 첫 요소를 시각적으로 잇기 위한 트릭
                    const isNextActual = group.data.find(d => d.period === allPeriods[allPeriods.indexOf(p)+1] && d.type === 'actual');
                    if (tItem && isNextActual) return tItem.ratio;
                    
                    return null;
                });

                // 3. 예측 데이터 (Predicted Test) - 점선
                const predictedData = allPeriods.map(p => {
                    const item = group.data.find(d => d.period === p && d.type === 'predicted');
                    if (item) return item.ratio;
                    
                    // 연결을 위해 train의 마지막 값 가져오기
                    const tItem = group.data.find(d => d.period === p && d.type === 'train');
                    const isNextPred = group.data.find(d => d.period === allPeriods[allPeriods.indexOf(p)+1] && d.type === 'predicted');
                    if (tItem && isNextPred) return tItem.ratio;
                    
                    return null;
                });

                series.push({ name: `${group.title} (과거 학습)`, data: trainData });
                strokeDashArray.push(0);
                strokeColors.push(trainColor);
                fillColors.push(trainColor);
                markerSizes.push(0);

                series.push({ name: `${group.title} (숨겨둔 실제 데이터)`, data: actualData });
                strokeDashArray.push(0);
                strokeColors.push(actualColor);
                fillColors.push(actualColor);
                markerSizes.push(0);

                series.push({ name: `${group.title} (AI 예측)`, data: predictedData });
                strokeDashArray.push(5);
                strokeColors.push(forecastColor);
                fillColors.push(forecastColor);
                markerSizes.push(0);

            } else {
                // 일반 모드 (과거 vs 미래)
                const actualData = allPeriods.map(p => {
                    const item = group.data.find(d => d.period === p && !d.isForecast);
                    return item ? item.ratio : null;
                });

                const forecastData = allPeriods.map((p, idx) => {
                    const item = group.data.find(d => d.period === p && d.isForecast);
                    if (item) return item.ratio;
                    
                    // 연결을 위해 과거 마지막 값 가져오기
                    const aItem = group.data.find(d => d.period === p && !d.isForecast);
                    const isNextFore = group.data.find(d => d.period === allPeriods[idx+1] && d.isForecast);
                    if (aItem && isNextFore) return aItem.ratio;
                    
                    return null;
                });

                // 신뢰구간 (상한/하한) 데이터 구성
                const upperData = [];
                const lowerData = [];
                
                allPeriods.forEach((p, idx) => {
                    const item = group.data.find(d => d.period === p && d.isForecast);
                    if (item && item.yhat_lower !== undefined && item.yhat_upper !== undefined) {
                        upperData.push(item.yhat_upper);
                        lowerData.push(item.yhat_lower);
                    } else {
                        // 연결부
                        const aItem = group.data.find(d => d.period === p && !d.isForecast);
                        const isNextFore = group.data.find(d => d.period === allPeriods[idx+1] && d.isForecast);
                        if (aItem && isNextFore) {
                            upperData.push(aItem.ratio);
                            lowerData.push(aItem.ratio);
                        } else {
                            upperData.push(null);
                            lowerData.push(null);
                        }
                    }
                });

                // 1. 예측 범위 (상한/하한 점선)
                const hasConfidence = upperData.some(val => val !== null);
                if (hasConfidence) {
                    series.push({ name: `${group.title} (예측 상한)`, type: 'line', data: upperData });
                    strokeDashArray.push(2);
                    strokeColors.push(fadeColor);
                    fillColors.push('transparent');
                    markerSizes.push(0);

                    series.push({ name: `${group.title} (예측 하한)`, type: 'line', data: lowerData });
                    strokeDashArray.push(2);
                    strokeColors.push(fadeColor);
                    fillColors.push('transparent');
                    markerSizes.push(0);
                }

                // 2. 과거 데이터
                series.push({ name: `${group.title} (과거)`, type: 'line', data: actualData });
                strokeDashArray.push(0);
                strokeColors.push('#6b7280'); // 과거 트렌드는 회색으로 통일
                fillColors.push('#6b7280');
                markerSizes.push(0);

                // 3. 예측 데이터
                series.push({ name: `${group.title} (예측)`, type: 'line', data: forecastData });
                strokeDashArray.push(5);
                strokeColors.push(color); // 미래 예측은 그룹 컬러(기본 민트색)
                fillColors.push(fadeColor);
                markerSizes.push(0);

                const signalData = allPeriods.map(period => {
                    const signal = signals.find(item => item.date === period);
                    if (!signal) return null;
                    const point = group.data.find(item => item.period === period && !item.isForecast);
                    return point ? point.ratio : null;
                });

                if (signalData.some(value => value !== null)) {
                    series.push({ name: `${group.title} (유행 전조 감지)`, type: 'scatter', data: signalData });
                    strokeDashArray.push(0);
                    strokeColors.push(signalColor);
                    fillColors.push(signalColor);
                    markerSizes.push(7);
                }
            }
        });

        const options = {
            series: series,
            chart: {
                type: 'line',
                height: 380,
                background: 'transparent',
                toolbar: {
                    show: true,
                    tools: {
                        download: true,
                        selection: false,
                        zoom: true,
                        zoomin: true,
                        zoomout: true,
                        pan: false,
                        reset: true
                    }
                },
                animations: {
                    enabled: true,
                    easing: 'easeinout',
                    speed: 800,
                    animateGradually: {
                        enabled: true,
                        delay: 150
                    },
                    dynamicAnimation: {
                        enabled: true,
                        speed: 350
                    }
                }
            },
            colors: strokeColors,
            stroke: {
                curve: 'smooth',
                width: series.map(s => {
                    if (s.name.includes('상한') || s.name.includes('하한')) return 1;
                    if (s.name.includes('유행 전조')) return 0;
                    return 3;
                }),
                dashArray: strokeDashArray
            },
            markers: {
                size: markerSizes,
                strokeColors: '#ffffff',
                strokeWidth: 2,
                hover: {
                    sizeOffset: 3
                }
            },
            fill: {
                type: 'solid',
                colors: fillColors
            },
            grid: {
                borderColor: 'rgba(0, 0, 0, 0.05)',
                xaxis: {
                    lines: {
                        show: false
                    }
                },
                yaxis: {
                    lines: {
                        show: true
                    }
                }
            },
            legend: {
                show: false // 커스텀 레전드를 사용하므로 끔
            },
            xaxis: {
                categories: allPeriods,
                labels: {
                    style: {
                        colors: '#6b7280',
                        fontSize: '11px'
                    },
                    rotate: -45,
                    trim: true
                },
                axisBorder: {
                    show: false
                },
                axisTicks: {
                    color: 'rgba(0, 0, 0, 0.1)'
                }
            },
            yaxis: {
                min: 0,
                tickAmount: 5,
                labels: {
                    style: {
                        colors: '#6b7280',
                        fontSize: '11px'
                    },
                    formatter: function(val) {
                        return val.toFixed(0);
                    }
                }
            },
            tooltip: {
                shared: true,
                intersect: false,
                custom: function({series, seriesIndex, dataPointIndex, w}) {
                    const data = w.globals.initialSeries;
                    const category = w.globals.categoryLabels[dataPointIndex];
                    
                    let html = `<div style="padding: 12px; background: rgba(255, 255, 255, 0.95); border: 1px solid var(--card-border); border-radius: 8px; box-shadow: var(--shadow-md); backdrop-filter: blur(4px);">`;
                    html += `<div style="margin-bottom: 10px; font-weight: 700; color: var(--text-muted); font-size: 12px;">${category}</div>`;
                    
                    data.forEach((s, idx) => {
                        const val = s.data[dataPointIndex];
                        if (val !== null && val !== undefined) {
                            // w.config.colors에 우리가 주입한 strokeColors가 들어있음
                            const color = w.config.colors[idx] || '#111827';
                            
                            // 상하한선처럼 투명도가 들어간 색상이면 그대로 쓰고, 아니면 그대로 씀
                            html += `<div style="display: flex; align-items: center; margin-bottom: 6px;">
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${color}; margin-right: 8px; box-shadow: 0 0 0 1px rgba(0,0,0,0.05);"></span>
                                <span style="font-size: 13px; color: var(--text-main); margin-right: 16px;">${s.name}</span>
                                <span style="font-weight: 700; font-size: 13px; color: var(--text-main); margin-left: auto;">${val.toFixed(0)}건</span>
                            </div>`;
                        }
                    });
                    
                    html += `</div>`;
                    return html;
                }
            },
            annotations: {
                points: signalAnnotations
            }
        };

        this.chart = new ApexCharts(document.querySelector(`#${this.containerId}`), options);
        this.chart.render();
    }
}
