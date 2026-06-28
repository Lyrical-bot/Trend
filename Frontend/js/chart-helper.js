class TrendChartHelper {
    constructor(containerId) {
        this.containerId = containerId;
        this.chart = null;
        // 그룹별 고유 컬러 팔레트 (Naver Bright Green, Purple, Coral)
        this.colors = ['#02e06b', '#6b52ff', '#ef4444'];
        this.colorsFade = ['rgba(2, 224, 107, 0.25)', 'rgba(107, 82, 255, 0.25)', 'rgba(239, 68, 68, 0.25)'];
        
        // 줌 컨트롤러 상태값
        this.absoluteMin = null;
        this.absoluteMax = null;
        this.currentMin = null;
        this.currentMax = null;
    }

    /**
     * 네이버 API 가공 데이터를 기반으로 차트를 그립니다.
     * results: [{ title, keywords, data: [{ period, ratio, isForecast, type }] }]
     */
    renderChart(results, isBacktest = false, weatherData = null, showTemp = false, showRain = false) {
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

        // --- 4개월 디폴트 줌 기간 계산 ---
        let defaultMin = null;
        let defaultMax = null;
        if (allPeriods.length > 0) {
            const maxTime = new Date(allPeriods[allPeriods.length - 1]).getTime();
            const minTime = maxTime - (120 * 24 * 60 * 60 * 1000); // 120일 전 (4개월)
            const absoluteMinTime = new Date(allPeriods[0]).getTime();

            this.absoluteMin = absoluteMinTime;
            this.absoluteMax = maxTime;
            this.currentMin = Math.max(absoluteMinTime, minTime);
            this.currentMax = maxTime;

            defaultMin = this.currentMin;
            defaultMax = this.currentMax;
        }

        results.forEach((group, index) => {
            const color = this.colors[index % this.colors.length];
            const fadeColor = this.colorsFade[index % this.colorsFade.length];
            const signals = Array.isArray(group.signals) ? group.signals : [];
            const trainColor = '#6b7280';
            const actualColor = '#3b82f6';
            const forecastColor = '#1abc9c';
            const signalColor = '#ef4444';

            // signals.forEach(signal => {
            //     const point = group.data.find(item => item.period === signal.date && !item.isForecast);
            //     if (!point) return;
            // 
            //     signalAnnotations.push({
            //         x: signal.date,
            //         y: point.ratio,
            //         marker: {
            //             size: 7,
            //             fillColor: signalColor,
            //             strokeColor: '#ffffff',
            //             strokeWidth: 2,
            //             radius: 2
            //         },
            //         label: {
            //             borderColor: signalColor,
            //             offsetY: 0,
            //             style: {
            //                 color: '#ffffff',
            //                 background: signalColor,
            //                 fontSize: '11px',
            //                 fontWeight: 700
            //             },
            //             text: `${signal.label || '유행 전조'} ${signal.score || ''}점`
            //         }
            //     });
            // });

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

        // 4. 날씨 정보 체크에 따른 series 추가 (CORS 및 이중 Y축 오버레이 데이터 연동)
        if (weatherData && weatherData.length > 0) {
            if (showTemp) {
                const tempData = allPeriods.map(p => {
                    const wItem = weatherData.find(w => w.period === p);
                    return wItem ? wItem.avgTa : null;
                });
                series.push({ name: "평균 기온 (°C)", type: 'line', data: tempData });
                strokeDashArray.push(0);
                strokeColors.push('#ef4444'); // 기온은 연한 빨강
                fillColors.push('#ef4444');
                markerSizes.push(0);
            }

            if (showRain) {
                const rainData = allPeriods.map(p => {
                    const wItem = weatherData.find(w => w.period === p);
                    return wItem ? wItem.sumRn : null;
                });
                series.push({ name: "일강수량 (mm)", type: 'bar', data: rainData });
                strokeDashArray.push(0);
                strokeColors.push('#3b82f6'); // 강수량은 연한 파랑
                fillColors.push('rgba(59, 130, 246, 0.4)');
                markerSizes.push(0);
            }
        }

        const options = {
            series: series,
            chart: {
                type: 'line',
                height: 380,
                background: 'transparent',
                toolbar: {
                    show: false,
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
                zoom: {
                    enabled: false
                },
                dropShadow: {
                    enabled: true,
                    top: 6,
                    left: 0,
                    blur: 6,
                    color: strokeColors.length > 0 ? strokeColors[0] : '#6b52ff',
                    opacity: 0.18
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
                    if (s.name.includes('평균 기온')) return 2;
                    if (s.name.includes('일강수량')) return 1.5;
                    if (s.name.includes('유행 전조')) return 0;
                    return 4.5; // 네이버 트렌드 및 예측 실선/점선을 4.5px로 극대화
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
                type: 'datetime',
                categories: allPeriods,
                min: defaultMin,
                max: defaultMax,
                labels: {
                    style: {
                        colors: '#6b7280',
                        fontSize: '11px'
                    },
                    datetimeFormatter: {
                        year: 'yyyy년',
                        month: "yyyy년 MM월",
                        day: 'MM.dd',
                        hour: 'HH:mm'
                    }
                },
                axisBorder: {
                    show: false
                },
                axisTicks: {
                    color: 'rgba(0, 0, 0, 0.1)'
                }
            },
            yaxis: (() => {
                let yaxisConfig = [];
                
                // 검색어 트렌드 시리즈 개수 파악
                const primarySeriesCount = series.filter(s => s.name !== "평균 기온 (°C)" && s.name !== "일강수량 (mm)").length;
                
                for (let i = 0; i < primarySeriesCount; i++) {
                    yaxisConfig.push({
                        show: i === 0,
                        min: 0,
                        tickAmount: 5,
                        labels: {
                            style: {
                                colors: '#6b7280',
                                fontSize: '11px'
                            },
                            formatter: function(val) {
                                return val !== null && val !== undefined ? val.toFixed(0) : '';
                            }
                        },
                        title: i === 0 ? {
                            text: "검색량 / 트렌드 비율",
                            style: {
                                color: '#6b7280',
                                fontWeight: 600
                            }
                        } : undefined
                    });
                }
                
                // 기온 Y축 (우측)
                if (showTemp) {
                    yaxisConfig.push({
                        opposite: true,
                        seriesName: "평균 기온 (°C)",
                        min: -15,
                        max: 40,
                        tickAmount: 5,
                        title: {
                            text: "평균 기온 (°C)",
                            style: {
                                color: '#ef4444',
                                fontWeight: 600
                            }
                        },
                        labels: {
                            style: {
                                colors: '#ef4444',
                                fontSize: '11px'
                            },
                            formatter: function(val) {
                                return val !== null && val !== undefined ? `${val.toFixed(1)}°C` : '';
                            }
                        }
                    });
                }
                
                // 강수량 Y축 (우측)
                if (showRain) {
                    yaxisConfig.push({
                        opposite: true,
                        seriesName: "일강수량 (mm)",
                        min: 0,
                        max: 100,
                        tickAmount: 5,
                        title: {
                            text: "일강수량 (mm)",
                            style: {
                                color: '#3b82f6',
                                fontWeight: 600
                            }
                        },
                        labels: {
                            style: {
                                colors: '#3b82f6',
                                fontSize: '11px'
                            },
                            formatter: function(val) {
                                return val !== null && val !== undefined ? `${val.toFixed(0)}mm` : '';
                            }
                        }
                    });
                }
                
                return yaxisConfig;
            })(),
            tooltip: {
                shared: true,
                intersect: false,
                custom: function({series, seriesIndex, dataPointIndex, w}) {
                    const data = w.globals.initialSeries;
                    let rawTime = (w.globals.seriesX && w.globals.seriesX[0]) ? w.globals.seriesX[0][dataPointIndex] : null;
                    let category = rawTime || w.globals.categoryLabels[dataPointIndex] || w.globals.labels[dataPointIndex];
                    
                    if (category && (typeof category === 'number' || (typeof category === 'string' && !isNaN(new Date(category).getTime())))) {
                        const d = new Date(category);
                        category = `${d.getFullYear()}년 ${String(d.getMonth()+1).padStart(2,'0')}월 ${String(d.getDate()).padStart(2,'0')}일`;
                    }
                    
                    let html = `<div style="padding: 12px; background: rgba(255, 255, 255, 0.97); border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); backdrop-filter: blur(4px);">`;
                    html += `<div style="margin-bottom: 10px; font-weight: 700; color: #6b7280; font-size: 12px;">${category}</div>`;
                    
                    data.forEach((s, idx) => {
                        let val = w.globals.series[idx] ? w.globals.series[idx][dataPointIndex] : null;
                        if (val === null || val === undefined) {
                            val = s.data[dataPointIndex];
                        }
                        if (val !== null && val !== undefined) {
                            const color = w.config.colors[idx] || '#111827';
                            let unit = '건';
                            let formattedVal = (typeof val === 'number') ? val.toFixed(0) : val;
                            
                            if (s.name.includes('기온')) {
                                unit = '°C';
                                formattedVal = (typeof val === 'number') ? val.toFixed(1) : val;
                            } else if (s.name.includes('강수량')) {
                                unit = 'mm';
                            }
                            
                            html += `<div style="display: flex; align-items: center; margin-bottom: 6px;">
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${color}; margin-right: 8px; box-shadow: 0 0 0 1px rgba(0,0,0,0.05);"></span>
                                <span style="font-size: 13px; color: #111827; margin-right: 16px;">${s.name}</span>
                                <span style="font-weight: 700; font-size: 13px; color: #111827; margin-left: auto;">${formattedVal}${unit}</span>
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

    /**
     * 차트 가로축의 줌 영역을 확대(In) 또는 축소(Out) 처리합니다.
     * direction: 'in' | 'out'
     */
    zoom(direction) {
        if (!this.chart || !this.currentMin || !this.currentMax || !this.absoluteMin || !this.absoluteMax) {
            console.warn("차트가 준비되지 않았거나 줌 상태값이 없습니다.");
            return;
        }

        const currentSpan = this.currentMax - this.currentMin;
        let newSpan = currentSpan;

        if (direction === 'in') {
            // 확대: 보여주는 구간(Span)을 절반으로 단축 (최소 7일 제한)
            newSpan = Math.max(7 * 24 * 60 * 60 * 1000, currentSpan / 2);
        } else if (direction === 'out') {
            // 축소: 보여주는 구간(Span)을 2배로 확장 (최대 전체 범위 제한)
            newSpan = Math.min(this.absoluteMax - this.absoluteMin, currentSpan * 2);
        }

        // 사용자가 집중하는 우측 영역(미래 예측 끝점)을 기준으로 좌측 범위를 동적 가감
        let newMin = this.absoluteMax - newSpan;
        let newMax = this.absoluteMax;

        if (newMin < this.absoluteMin) {
            newMin = this.absoluteMin;
        }

        this.currentMin = newMin;
        this.currentMax = newMax;

        // ApexCharts zoomX API 호출
        this.chart.zoomX(newMin, newMax);
    }
}
