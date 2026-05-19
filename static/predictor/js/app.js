const resetButton = document.getElementById("reset-btn");
const themeToggle = document.getElementById("theme-toggle");

const savedTheme = localStorage.getItem("houseprice-theme");
if (savedTheme === "dark") {
    document.body.classList.add("dark-mode");
    if (themeToggle) {
        themeToggle.textContent = "Light mode";
    }
}

if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const isDark = document.body.classList.toggle("dark-mode");
        localStorage.setItem("houseprice-theme", isDark ? "dark" : "light");
        themeToggle.textContent = isDark ? "Light mode" : "Dark mode";
    });
}

if (resetButton) {
    resetButton.addEventListener("click", () => {
        document.getElementById("area_m2").value = 100;
        document.getElementById("floors").value = 1;
        document.getElementById("rooms").value = 4;
        document.getElementById("bedrooms").value = 2;
        document.getElementById("district").value = "Cam Le";
    });
}

const chartDataElement = document.getElementById("chart-data");

if (chartDataElement && window.Chart) {
    const chartData = JSON.parse(chartDataElement.textContent || "{}");
    const labels = chartData.labels || [];

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: "rgba(13, 110, 253, 0.08)"
                }
            },
            x: {
                grid: {
                    display: false
                }
            }
        }
    };

    const countCanvas = document.getElementById("districtCountChart");
    if (countCanvas) {
        new Chart(countCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Số mẫu",
                    data: chartData.counts || [],
                    backgroundColor: "#0d6efd",
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                plugins: {
                    title: {
                        display: true,
                        text: "Số lượng mẫu theo quận/huyện"
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    const priceCanvas = document.getElementById("avgPriceChart");
    if (priceCanvas) {
        new Chart(priceCanvas, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Giá trung bình",
                    data: chartData.avg_prices || [],
                    borderColor: "#0d6efd",
                    backgroundColor: "rgba(13, 110, 253, 0.12)",
                    tension: 0.32,
                    fill: true,
                    pointRadius: 4
                }]
            },
            options: {
                ...commonOptions,
                plugins: {
                    title: {
                        display: true,
                        text: "Giá trung bình theo quận/huyện (triệu VND)"
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}
