// ── Theme ──
const themeToggle = document.getElementById("theme-toggle");
const savedTheme = localStorage.getItem("houseprice-theme");
if (savedTheme === "dark") {
    document.body.classList.add("dark-mode");
    if (themeToggle) themeToggle.textContent = "☀️";
}
if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const isDark = document.body.classList.toggle("dark-mode");
        localStorage.setItem("houseprice-theme", isDark ? "dark" : "light");
        themeToggle.textContent = isDark ? "☀️" : "🌙";
    });
}

// ── Reset form ──
const resetButton = document.getElementById("reset-btn");
if (resetButton) {
    resetButton.addEventListener("click", () => {
        document.getElementById("area_m2").value = 100;
        document.getElementById("floors").value = 3;
        document.getElementById("rooms").value = 5;
        document.getElementById("bedrooms").value = 3;
        document.getElementById("district").selectedIndex = 0;
    });
}

// ── Hero Slideshow ──
const slides = document.querySelectorAll(".hero-slide");
const dotsContainer = document.getElementById("hero-dots");
let current = 0;
let timer;

if (slides.length > 1) {
    // Tạo dots
    slides.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.className = "hero-dot" + (i === 0 ? " active" : "");
        dot.addEventListener("click", () => goTo(i));
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

// ── Charts ──
const chartDataElement = document.getElementById("chart-data");
if (chartDataElement && window.Chart) {
    const chartData = JSON.parse(chartDataElement.textContent || "{}");
    const labels = chartData.labels || [];
    const isDark = () => document.body.classList.contains("dark-mode");

    const commonOptions = (title) => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            title: {
                display: true,
                text: title,
                font: { size: 13, weight: "700" },
                color: isDark() ? "#eaf2ff" : "#172033",
                padding: { bottom: 16 }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: isDark() ? "rgba(180,210,255,0.08)" : "rgba(13,110,253,0.07)" },
                ticks: { color: isDark() ? "#adc3dd" : "#5d6b82", font: { size: 11 } }
            },
            x: {
                grid: { display: false },
                ticks: { color: isDark() ? "#adc3dd" : "#5d6b82", font: { size: 11 } }
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
            options: commonOptions("Số lượng mẫu theo quận/huyện")
        });
    }

    const priceCanvas = document.getElementById("avgPriceChart");
    if (priceCanvas) {
        new Chart(priceCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Giá TB (triệu)",
                    data: chartData.avg_prices || [],
                    backgroundColor: "rgba(8,66,152,0.7)",
                    hoverBackgroundColor: "#084298",
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: commonOptions("Giá trung bình theo quận/huyện (triệu VND)")
        });
    }
}