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

    const regressionCanvas = document.getElementById("regressionScatterChart");
    if (regressionCanvas) {
        new Chart(regressionCanvas, {
            type: "scatter",
            data: {
                datasets: [
                    {
                        label: "Du lieu that",
                        data: chartData.scatter_points || [],
                        backgroundColor: "rgba(13,110,253,0.32)",
                        borderColor: "rgba(13,110,253,0.45)",
                        pointRadius: 3,
                        pointHoverRadius: 5
                    },
                    {
                        type: "line",
                        label: "Duong hoi quy",
                        data: chartData.regression_line || [],
                        borderColor: "#dc3545",
                        backgroundColor: "#dc3545",
                        borderWidth: 3,
                        pointRadius: 0,
                        tension: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: axisColor(), font: { size: 12, weight: "700" } }
                    },
                    title: {
                        display: true,
                        text: "Minh hoa Linear Regression: dien tich va gia dat",
                        font: { size: 13, weight: "700" },
                        color: titleColor(),
                        padding: { bottom: 16 }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const point = context.raw || {};
                                return `${context.dataset.label}: ${point.x} m2, ${Math.round(point.y)} trieu`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: "linear",
                        title: { display: true, text: "Dien tich (m2)", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor(), font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: "Gia dat (trieu VND)", color: axisColor() },
                        grid: { color: gridColor() },
                        ticks: { color: axisColor(), font: { size: 11 } }
                    }
                }
            }
        });
    }

    const countCanvas = document.getElementById("districtCountChart");
    if (countCanvas) {
        new Chart(countCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "So mau",
                    data: chartData.counts || [],
                    backgroundColor: "rgba(13,110,253,0.75)",
                    hoverBackgroundColor: "#0d6efd",
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: commonOptions("So luong mau dat theo quan/huyen")
        });
    }

    const priceCanvas = document.getElementById("avgPriceChart");
    if (priceCanvas) {
        new Chart(priceCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Gia TB (trieu)",
                    data: chartData.avg_prices || [],
                    backgroundColor: "rgba(8,66,152,0.7)",
                    hoverBackgroundColor: "#084298",
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: commonOptions("Gia dat trung binh theo quan/huyen (trieu VND)")
        });
    }
}
