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
     * results: [{ title, keywords, data: [{ period, ratio, isForecast }] }]
     */
    renderChart(results) {
        if (this.chart) {
            this.chart.destroy();
        }

        const series = [];
        const strokeDashArray = [];
        const strokeColors = [];
        const fillColors = [];
        
        let allPeriods = [];

        // 모든 날짜 목록 수집 및 정렬
        if (results.length > 0) {
            allPeriods = results[0].data.map(item => item.period);
        }

        results.forEach((group, index) => {
            const color = this.colors[index % this.colors.length];
            const fadeColor = this.colorsFade[index % this.colorsFade.length];

            // 1. 과거(실제) 데이터 시리즈
            const actualData = group.data.map(item => {
                return item.isForecast ? null : item.ratio;
            });

            // 2. 예측 데이터 시리즈
            // 자연스러운 연결을 위해 과거 마지막 데이터 포인트를 예측 데이터의 첫 부분에 결합시킵니다.
            let lastActualIdx = -1;
            for (let i = group.data.length - 1; i >= 0; i--) {
                if (!group.data[i].isForecast) {
                    lastActualIdx = i;
                    break;
                }
            }

            const forecastData = group.data.map((item, idx) => {
                if (item.isForecast) {
                    return item.ratio;
                }
                // 예측의 시작점을 과거 마지막 데이터로 연결
                if (idx === lastActualIdx) {
                    return item.ratio;
                }
                return null;
            });

            // 과거 시리즈 추가 (실선)
            series.push({
                name: `${group.title} (과거)`,
                data: actualData
            });
            strokeDashArray.push(0); // 0 = 실선
            strokeColors.push(color);
            fillColors.push(color);

            // 예측 시리즈 추가 (점선)
            series.push({
                name: `${group.title} (예측)`,
                data: forecastData
            });
            strokeDashArray.push(5); // 5 = 점선 크기
            strokeColors.push(color);
            fillColors.push(fadeColor);
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
