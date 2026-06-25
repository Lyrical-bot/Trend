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
        
        let allPeriods = [];

        // 모든 날짜 목록 수집 및 정렬 (중복 제거)
        if (results.length > 0) {
            allPeriods = Array.from(new Set(results[0].data.map(item => item.period))).sort();
        }

        results.forEach((group, index) => {
            const color = this.colors[index % this.colors.length];
            const fadeColor = this.colorsFade[index % this.colorsFade.length];

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
                strokeColors.push(color);
                fillColors.push(color);

                series.push({ name: `${group.title} (숨겨둔 실제 데이터)`, data: actualData });
                strokeDashArray.push(0);
                strokeColors.push('#3b82f6'); // 파란색 실선으로 실제 데이터 강조
                fillColors.push('#3b82f6');

                series.push({ name: `${group.title} (AI 예측)`, data: predictedData });
                strokeDashArray.push(5);
                strokeColors.push(color);
                fillColors.push(fadeColor);

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

                series.push({ name: `${group.title} (과거)`, data: actualData });
                strokeDashArray.push(0);
                strokeColors.push(color);
                fillColors.push(color);

                series.push({ name: `${group.title} (예측)`, data: forecastData });
                strokeDashArray.push(5);
                strokeColors.push(color);
                fillColors.push(fadeColor);
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
                width: 3,
                dashArray: strokeDashArray
            },
            fill: {
                type: 'solid'
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
                theme: 'light',
                shared: true,
                intersect: false,
                x: {
                    show: true
                },
                y: {
                    formatter: function(val) {
                        return val !== null ? val.toFixed(0) + '건' : undefined;
                    }
                }
            }
        };

        this.chart = new ApexCharts(document.querySelector(`#${this.containerId}`), options);
        this.chart.render();
    }
}
