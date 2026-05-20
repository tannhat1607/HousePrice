from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


TARGET = "price_million_vnd"
PRICE_PER_M2 = "price_per_m2_million"

# Cac feature dau vao cua model du doan gia dat.
# area_x_frontage la feature tu tao: dien tich * mat tien.
FEATURES = ["area_m2", "frontage_m", "road_width_m", "district_code", "area_x_frontage"]

DISTRICTS = {
    "Hai Chau": 1,
    "Thanh Khe": 2,
    "Son Tra": 3,
    "Ngu Hanh Son": 4,
    "Lien Chieu": 5,
    "Cam Le": 6,
    "Hoa Vang": 7,
}


@dataclass
class PredictionResult:
    price_million_vnd: float
    price_billion_vnd: float
    price_per_m2_million: float


def predict(X, weights):
    # Cong thuc Linear Regression: y_hat = X.w
    return np.dot(X, weights)


def cost_function(X, y, weights):
    # Ham mat mat MSE: trung binh binh phuong sai so.
    error = predict(X, weights) - y
    return np.mean(error ** 2)


def update_weights(X, y, weights, learning_rate):
    # Cap nhat weights bang Gradient Descent.
    error = predict(X, weights) - y
    gradient = (2 / len(y)) * np.dot(X.T, error)
    return weights - learning_rate * gradient


def add_bias(X):
    # Them cot 1 vao dau X de model hoc he so intercept.
    return np.hstack((np.ones((X.shape[0], 1)), X))


def train(X_train, y_train, X_test, y_test, epochs=3000, learning_rate=0.003):
    weights = np.zeros(X_train.shape[1])
    train_history = []
    test_history = []

    for _ in range(epochs):
        # Moi epoch: cap nhat weights, sau do luu loss train/test.
        weights = update_weights(X_train, y_train, weights, learning_rate)
        train_history.append(cost_function(X_train, y_train, weights))
        test_history.append(cost_function(X_test, y_test, weights))

    return weights, train_history, test_history


def load_land_data(dataset_path):
    # Doc dataset sach va chi giu cac cot can thiet cho bai toan gia dat.
    df = pd.read_csv(dataset_path)

    required_cols = [
        "area_m2",
        "frontage_m",
        "road_width_m",
        "district",
        "district_code",
        TARGET,
        PRICE_PER_M2,
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Dataset thieu cot: {', '.join(missing)}")

    if "property_type" in df.columns:
        # Dataset hien tai chi dung dat, bo cac dong khac neu co.
        df = df[df["property_type"] == "land"].copy()

    for col in required_cols:
        if col != "district":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required_cols)

    # Feature engineering: lo dat co mat tien lon tren dien tich lon thuong co gia tri cao hon.
    df["area_x_frontage"] = df["area_m2"] * df["frontage_m"]

    # Loc cac gia tri qua bat thuong truoc khi train.
    df = df[
        (df["area_m2"].between(20, 5000))
        & (df["frontage_m"].between(0, 100))
        & (df["road_width_m"].between(0, 100))
        & (df["district_code"].between(1, 7))
        & (df[TARGET].between(100, 200000))
    ].copy()

    q05 = df[PRICE_PER_M2].quantile(0.05)
    q95 = df[PRICE_PER_M2].quantile(0.95)
    # Cat 5% thap nhat va 5% cao nhat theo don gia de giam outlier.
    df = df[(df[PRICE_PER_M2] >= q05) & (df[PRICE_PER_M2] <= q95)].copy()

    if len(df) < 20:
        raise ValueError("Dataset dat qua it dong de train model.")

    return df


def split_train_test(X, y, test_ratio=0.2):
    # Chia du lieu ngau nhien: 80% train, 20% test.
    np.random.seed(42)
    indices = np.arange(len(X))
    np.random.shuffle(indices)

    test_size = int(test_ratio * len(indices))
    test_idx = indices[:test_size]
    train_idx = indices[test_size:]

    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


def normalize_train_test(train_values, test_values):
    # Chuan hoa theo mean/std cua tap train de tranh leak thong tin test.
    mean = train_values.mean(axis=0)
    std = train_values.std(axis=0)
    std = np.where(std == 0, 1, std)

    train_scaled = (train_values - mean) / std
    test_scaled = (test_values - mean) / std

    return train_scaled, test_scaled, mean, std


def metrics(y_true, y_pred):
    # Cac chi so danh gia model tren tap test.
    error = y_true - y_pred
    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))
    ss_res = np.sum(error ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    return mae, rmse, r2


class LinearRegressionModel:
    def __init__(self, dataset_path: Path):
        self.dataset_path = Path(dataset_path)
        self.df = load_land_data(self.dataset_path)

        # Tao X, y tu dataset da loc.
        X = np.nan_to_num(self.df[FEATURES].values, nan=0)
        y = np.nan_to_num(self.df[TARGET].values, nan=0)

        # Chia train/test va chuan hoa X, y.
        X_train, X_test, y_train, y_test = split_train_test(X, y)
        X_train, X_test, self.X_mean, self.X_std = normalize_train_test(X_train, X_test)
        y_train, y_test, self.y_mean, self.y_std = normalize_train_test(y_train, y_test)

        # Them bias sau khi chuan hoa.
        X_train = add_bias(X_train)
        X_test = add_bias(X_test)

        # Train model Linear Regression bang NumPy.
        self.weights, self.train_history, self.test_history = train(X_train, y_train, X_test, y_test)

        # Dua y ve don vi trieu VND de tinh metric that.
        y_pred = predict(X_test, self.weights) * self.y_std + self.y_mean
        y_test_real = y_test * self.y_std + self.y_mean

        self.mae, self.rmse, self.r2 = metrics(y_test_real, y_pred)
        self.row_count = len(self.df)
        self.train_count = len(X_train)
        self.test_count = len(X_test)

        # Du lieu thong ke phuc vu bieu do tren giao dien.
        self.district_counts = self.df["district"].value_counts().to_dict()
        self.avg_price_by_district = self.df.groupby("district")[TARGET].mean().round(2).to_dict()
        self.avg_area_by_district = self.df.groupby("district")["area_m2"].mean().round(2).to_dict()
        self.scatter_points, self.regression_line_points = self.make_regression_chart()

    def make_regression_chart(self):
        # Bieu do minh hoa moi quan he dien tich - gia dat.
        # Model chinh van dung nhieu feature, duong nay chi de truc quan hoa.
        chart_df = self.df[["area_m2", TARGET]].dropna().copy()
        chart_df = chart_df[
            (chart_df["area_m2"] <= chart_df["area_m2"].quantile(0.98))
            & (chart_df[TARGET] <= chart_df[TARGET].quantile(0.98))
        ]

        if len(chart_df) > 350:
            chart_df = chart_df.sample(350, random_state=42)

        scatter_points = [
            {"x": round(float(row.area_m2), 2), "y": round(float(row.price_million_vnd), 2)}
            for row in chart_df.itertuples(index=False)
        ]

        x = chart_df["area_m2"].to_numpy(dtype=float)
        y = chart_df[TARGET].to_numpy(dtype=float)
        if len(x) < 2:
            return scatter_points, []

        slope, intercept = np.polyfit(x, y, 1)
        x_min = float(x.min())
        x_max = float(x.max())
        line_points = [
            {"x": round(x_min, 2), "y": round(max(float(slope * x_min + intercept), 0), 2)},
            {"x": round(x_max, 2), "y": round(max(float(slope * x_max + intercept), 0), 2)},
        ]

        return scatter_points, line_points

    def chart_data(self):
        # Tra ve JSON-friendly data cho Chart.js o frontend.
        labels = list(DISTRICTS.keys())
        return {
            "labels": labels,
            "counts": [int(self.district_counts.get(label, 0)) for label in labels],
            "avg_prices": [float(self.avg_price_by_district.get(label, 0)) for label in labels],
            "avg_areas": [float(self.avg_area_by_district.get(label, 0)) for label in labels],
            "scatter_points": self.scatter_points,
            "regression_line": self.regression_line_points,
        }

    def predict(self, area_m2: float, frontage_m: float, road_width_m: float, district: str) -> PredictionResult:
        if district not in DISTRICTS:
            raise ValueError("Quan/huyen khong hop le.")

        # Tao 1 dong du lieu moi dung cung thu tu FEATURES luc train.
        X_new = np.array(
            [[area_m2, frontage_m, road_width_m, DISTRICTS[district], area_m2 * frontage_m]],
            dtype=float,
        )
        # Chuan hoa du lieu moi bang mean/std da hoc tu tap train.
        X_new = (X_new - self.X_mean) / self.X_std
        X_new = add_bias(X_new)

        # Du doan xong dua ve don vi trieu VND.
        price_million = float(predict(X_new, self.weights)[0] * self.y_std + self.y_mean)
        price_million = max(price_million, 0)

        return PredictionResult(
            price_million_vnd=price_million,
            price_billion_vnd=price_million / 1000,
            price_per_m2_million=price_million / area_m2 if area_m2 else 0,
        )


_MODEL_CACHE: LinearRegressionModel | None = None
_MODEL_MTIME: float | None = None


def get_model(dataset_path: Path) -> LinearRegressionModel:
    global _MODEL_CACHE, _MODEL_MTIME

    dataset_path = Path(dataset_path)
    mtime = dataset_path.stat().st_mtime if dataset_path.exists() else None

    # Cache model de moi request web khong phai train lai.
    # Neu file dataset doi timestamp thi train lai model.
    if _MODEL_CACHE is None or _MODEL_MTIME != mtime:
        _MODEL_CACHE = LinearRegressionModel(dataset_path)
        _MODEL_MTIME = mtime

    return _MODEL_CACHE
