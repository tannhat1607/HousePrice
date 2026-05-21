const themeToggle = document.getElementById("theme-toggle");
const savedTheme = localStorage.getItem("landprice-theme");

if (savedTheme === "dark") {
    document.body.classList.add("dark-mode");
    if (themeToggle) themeToggle.textContent = "Light";
}

if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const isDark = document.body.classList.toggle("dark-mode");
        localStorage.setItem("landprice-theme", isDark ? "dark" : "light");
        themeToggle.textContent = isDark ? "Light" : "Dark";
    });
}

const resetButton = document.getElementById("reset-btn");
if (resetButton) {
    resetButton.addEventListener("click", () => {
        document.getElementById("area_m2").value = 100;
        document.getElementById("frontage_m").value = 5;
        document.getElementById("road_width_m").value = 7.5;
        document.getElementById("district").value = "Cam Le";
        const algorithm = document.getElementById("algorithm");
        if (algorithm) algorithm.value = "linear";
    });
}

const slides = document.querySelectorAll(".hero-slide");
const dotsContainer = document.getElementById("hero-dots");
let current = 0;
let timer;

if (slides.length > 1 && dotsContainer) {
    slides.forEach((_, index) => {
        const dot = document.createElement("button");
        dot.className = "hero-dot" + (index === 0 ? " active" : "");
        dot.type = "button";
        dot.addEventListener("click", () => goTo(index));
        dotsContainer.appendChild(dot);
    });

    function goTo(index) {
        slides[current].classList.remove("active");
        dotsContainer.children[current].classList.remove("active");
        current = (index + slides.length) % slides.length;
        slides[current].classList.add("active");
        dotsContainer.children[current].classList.add("active");
        resetTimer();
    }

    function resetTimer() {
        clearInterval(timer);
        timer = setInterval(() => goTo(current + 1), 4000);
    }

    resetTimer();
}

const chartDataElement = document.getElementById("chart-data");
if (chartDataElement && window.Chart) {
    const chartData = JSON.parse(chartDataElement.textContent || "{}");
    const labels = chartData.labels || [];
    const isDark = () => document.body.classList.contains("dark-mode");
    const axisColor = () => (isDark() ? "#adc3dd" : "#5d6b82");
    const gridColor = () => (isDark() ? "rgba(180,210,255,0.08)" : "rgba(13,110,253,0.07)");
    const titleColor = () => (isDark() ? "#eaf2ff" : "#172033");

    const commonOptions = (title) => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            title: {
                display: true,
                text: title,
                font: { size: 13, weight: "700" },
                color: titleColor(),
                padding: { bottom: 16 }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: gridColor() },
                ticks: { color: axisColor(), font: { size: 11 } }
            },
            x: {
                grid: { display: false },
                ticks: { color: axisColor(), font: { size: 11 } }
            }
        }
    });

    const countCanvas = document.getElementById("districtCountChart");
    if (countCanvas) {
        new Chart(countCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Số mẫu",
                    data: chartData.counts || [],
                    backgroundColor: "rgba(13,110,253,0.75)",
                    hoverBackgroundColor: "#0d6efd",
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: commonOptions("Số lượng mẫu đất theo quận/huyện")
        });
    }

    const priceCanvas = document.getElementById("avgPriceChart");
    if (priceCanvas) {
        new Chart(priceCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Đơn giá TB (triệu/m²)",
                    data: chartData.avg_prices || [],
                    backgroundColor: "rgba(8,66,152,0.7)",
                    hoverBackgroundColor: "#084298",
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: commonOptions("Đơn giá đất trung bình theo quận/huyện (triệu/m²)")
        });
    }

    const lossCanvas = document.getElementById("lossChart");
    if (lossCanvas) {
        new Chart(lossCanvas, {
            type: "line",
            data: {
                datasets: [
                    {
                        label: "Train Loss",
                        data: chartData.loss?.train || [],
                        borderColor: "#0d6efd",
                        backgroundColor: "rgba(13,110,253,0.12)",
                        borderWidth: 2,
                        pointRadius: 0
                    },
                    {
                        label: "Test Loss",
                        data: chartData.loss?.test || [],
                        borderColor: "#dc3545",
                        backgroundColor: "rgba(220,53,69,0.12)",
                        borderWidth: 2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, labels: { color: axisColor() } },
                    title: { display: true, text: "Loss theo epoch", color: titleColor() }
                },
                scales: {
                    x: {
                        type: "linear",
                        title: { display: true, text: "Epoch", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor() }
                    },
                    y: {
                        title: { display: true, text: "MSE Loss", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor() }
                    }
                }
            }
        });
    }

    const actualCanvas = document.getElementById("actualPredictedChart");
    if (actualCanvas) {
        const points = chartData.actual_predicted || [];
        const maxValue = Math.max(1, ...points.flatMap((point) => [point.x, point.y]));
        new Chart(actualCanvas, {
            type: "scatter",
            data: {
                datasets: [
                    {
                        label: "Actual vs Predicted",
                        data: points,
                        backgroundColor: "rgba(13,110,253,0.35)",
                        borderColor: "rgba(13,110,253,0.6)",
                        pointRadius: 3
                    },
                    {
                        type: "line",
                        label: "Đường lý tưởng",
                        data: [{ x: 0, y: 0 }, { x: maxValue, y: maxValue }],
                        borderColor: "#dc3545",
                        borderWidth: 2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, labels: { color: axisColor() } },
                    title: { display: true, text: "Đơn giá thật và đơn giá dự đoán", color: titleColor() }
                },
                scales: {
                    x: {
                        type: "linear",
                        title: { display: true, text: "Actual (triệu/m²)", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor() }
                    },
                    y: {
                        title: { display: true, text: "Predicted (triệu/m²)", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor() }
                    }
                }
            }
        });
    }

    const heatmap = document.getElementById("correlationHeatmap");
    if (heatmap) {
        const heatmapLabels = chartData.heatmap_labels || [];
        const points = chartData.heatmap_points || [];
        heatmap.style.gridTemplateColumns = `130px repeat(${heatmapLabels.length}, minmax(92px, 1fr))`;
        heatmap.innerHTML = `<div></div>${heatmapLabels.map((label) => `<strong>${label}</strong>`).join("")}`;

        heatmapLabels.forEach((rowLabel) => {
            heatmap.insertAdjacentHTML("beforeend", `<strong>${rowLabel}</strong>`);
            heatmapLabels.forEach((colLabel) => {
                const point = points.find((item) => item.x === colLabel && item.y === rowLabel) || { v: 0 };
                const alpha = Math.min(Math.abs(point.v), 1);
                const color = point.v >= 0
                    ? `rgba(13,110,253,${0.12 + alpha * 0.78})`
                    : `rgba(220,53,69,${0.12 + alpha * 0.78})`;
                heatmap.insertAdjacentHTML(
                    "beforeend",
                    `<span style="background:${color}">${point.v.toFixed(2)}</span>`
                );
            });
        });
    }
}
