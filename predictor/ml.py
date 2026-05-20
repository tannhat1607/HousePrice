from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "property_type_code",
    "area_m2",
    "frontage_m",
    "road_width_m",
    "floors",
    "bedrooms",
    "rooms",
    "district_code",
]
TARGET_COLUMN = "price_million_vnd"

PROPERTY_TYPES = {
    "land": "Đất",
    "house": "Nhà",
}
PROPERTY_TYPE_CODES = {
    "land": 0,
    "house": 1,
}
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


class LinearRegressionModel:
    """
    Linear Regression tự xây dựng bằng NumPy.

    Các bước:
    1. Chọn X, y
    2. Chia train/test
    3. Chuẩn hóa
    4. Tạo model: y_hat = X.w + b
    5. Train bằng Gradient Descent
    6. Predict
    7. Đánh giá
    8. Dự đoán dữ liệu mới
    """

    def __init__(self, dataset_path: Path, learning_rate: float = 0.03, epochs: int = 3000):
        self.dataset_path = Path(dataset_path)
        self.learning_rate = learning_rate
        self.epochs = epochs

        self.weights: np.ndarray | None = None
        self.bias = 0.0
        self.x_mean: np.ndarray | None = None
        self.x_std: np.ndarray | None = None
        self.y_mean = 0.0
        self.y_std = 1.0

        self.row_count = 0
        self.train_count = 0
        self.test_count = 0
        self.loss_history: list[float] = []
        self.rmse = 0.0
        self.mae = 0.0
        self.r2 = 0.0

        self.district_counts: dict[str, int] = {}
        self.avg_price_by_district: dict[str, float] = {}
        self.avg_area_by_district: dict[str, float] = {}
        self.type_counts: dict[str, int] = {}
        self.scatter_points: list[dict[str, float]] = []
        self.regression_line_points: list[dict[str, float]] = []

        self.train()

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(self.dataset_path)
        required_columns = FEATURE_COLUMNS + [TARGET_COLUMN, "district", "property_type"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Dataset thiếu cột: {', '.join(missing_columns)}")

        for col in FEATURE_COLUMNS + [TARGET_COLUMN]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required_columns)
        df = df[
            (df["property_type_code"].between(0, 1))
            & (df["area_m2"].between(20, 5000))
            & (df["frontage_m"].between(0, 100))
            & (df["road_width_m"].between(0, 100))
            & (df["floors"].between(0, 30))
            & (df["bedrooms"].between(0, 30))
            & (df["rooms"].between(0, 50))
            & (df["district_code"].between(1, 7))
            & (df[TARGET_COLUMN].between(100, 200000))
        ].copy()

        if len(df) < 20:
            raise ValueError("Dataset quá ít dòng hợp lệ để train model.")

        return df

    def summarize_data(self, df: pd.DataFrame) -> None:
        self.row_count = len(df)
        self.district_counts = df["district"].value_counts().to_dict()
        self.avg_price_by_district = df.groupby("district")[TARGET_COLUMN].mean().round(2).to_dict()
        self.avg_area_by_district = df.groupby("district")["area_m2"].mean().round(2).to_dict()
        self.type_counts = df["property_type"].value_counts().to_dict()
        self.prepare_regression_chart(df)

    def prepare_regression_chart(self, df: pd.DataFrame) -> None:
        # Bieu do 2D minh hoa Linear Regression theo rieng feature dien tich.
        # Model chinh van hoc nhieu feature, nhung bieu do nay giup nhin truc quan
        # cac diem du lieu va mot duong hoi quy thang.
        chart_df = df[["area_m2", TARGET_COLUMN]].dropna().copy()
        chart_df = chart_df[
            (chart_df["area_m2"] <= chart_df["area_m2"].quantile(0.98))
            & (chart_df[TARGET_COLUMN] <= chart_df[TARGET_COLUMN].quantile(0.98))
        ]

        if len(chart_df) > 350:
            chart_df = chart_df.sample(350, random_state=42)

        self.scatter_points = [
            {"x": round(float(row.area_m2), 2), "y": round(float(row.price_million_vnd), 2)}
            for row in chart_df.itertuples(index=False)
        ]

        x = chart_df["area_m2"].to_numpy(dtype=float)
        y = chart_df[TARGET_COLUMN].to_numpy(dtype=float)
        if len(x) < 2:
            self.regression_line_points = []
            return

        slope, intercept = np.polyfit(x, y, 1)
        x_min = float(np.min(x))
        x_max = float(np.max(x))
        self.regression_line_points = [
            {"x": round(x_min, 2), "y": round(max(float(slope * x_min + intercept), 0.0), 2)},
            {"x": round(x_max, 2), "y": round(max(float(slope * x_max + intercept), 0.0), 2)},
        ]

    def chart_data(self) -> dict:
        district_labels = list(DISTRICTS.keys())
        type_labels = list(PROPERTY_TYPES.keys())
        return {
            "labels": district_labels,
            "counts": [int(self.district_counts.get(label, 0)) for label in district_labels],
            "avg_prices": [float(self.avg_price_by_district.get(label, 0)) for label in district_labels],
            "avg_areas": [float(self.avg_area_by_district.get(label, 0)) for label in district_labels],
            "type_labels": [PROPERTY_TYPES[label] for label in type_labels],
            "type_counts": [int(self.type_counts.get(label, 0)) for label in type_labels],
            "scatter_points": self.scatter_points,
            "regression_line": self.regression_line_points,
        }

    def select_x_y(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = df[FEATURE_COLUMNS].to_numpy(dtype=float)
        y = df[TARGET_COLUMN].to_numpy(dtype=float)
        return x, y

    def split_train_test(
        self,
        x: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)
        indexes = rng.permutation(len(x))
        split_at = int(len(indexes) * (1 - test_size))
        train_indexes = indexes[:split_at]
        test_indexes = indexes[split_at:]
        return x[train_indexes], x[test_indexes], y[train_indexes], y[test_indexes]

    def fit_scaler(self, x_train: np.ndarray, y_train: np.ndarray) -> None:
        self.x_mean = x_train.mean(axis=0)
        self.x_std = x_train.std(axis=0)
        self.x_std[self.x_std == 0] = 1.0

        y_log = np.log1p(y_train)
        self.y_mean = float(y_log.mean())
        self.y_std = float(y_log.std()) or 1.0

    def scale_x(self, x: np.ndarray) -> np.ndarray:
        if self.x_mean is None or self.x_std is None:
            raise RuntimeError("Chưa chuẩn hóa X.")
        return (x - self.x_mean) / self.x_std

    def scale_y(self, y: np.ndarray) -> np.ndarray:
        y_log = np.log1p(y)
        return (y_log - self.y_mean) / self.y_std

    def unscale_y(self, y_scaled: np.ndarray) -> np.ndarray:
        y_log = y_scaled * self.y_std + self.y_mean
        return np.expm1(y_log)

    def predict_scaled(self, x: np.ndarray) -> np.ndarray:
        if self.weights is None:
            raise RuntimeError("Model chưa được tạo.")
        return x @ self.weights + self.bias

    def loss(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean((y_pred - y_true) ** 2))

    def update_weights(self, x: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        if self.weights is None:
            raise RuntimeError("Model chưa được tạo.")

        n = len(y_true)
        error = y_pred - y_true
        dw = (2 / n) * (x.T @ error)
        db = float((2 / n) * np.sum(error))

        self.weights -= self.learning_rate * dw
        self.bias -= self.learning_rate * db

    def train(self) -> None:
        df = self.load_data()
        self.summarize_data(df)

        x, y = self.select_x_y(df)
        x_train, x_test, y_train, y_test = self.split_train_test(x, y)
        self.train_count = len(x_train)
        self.test_count = len(x_test)

        self.fit_scaler(x_train, y_train)
        x_train_scaled = self.scale_x(x_train)
        x_test_scaled = self.scale_x(x_test)
        y_train_scaled = self.scale_y(y_train)

        self.weights = np.zeros(x_train_scaled.shape[1], dtype=float)
        self.bias = 0.0
        self.loss_history = []

        for _ in range(self.epochs):
            y_pred_scaled = self.predict_scaled(x_train_scaled)
            self.loss_history.append(self.loss(y_train_scaled, y_pred_scaled))
            self.update_weights(x_train_scaled, y_train_scaled, y_pred_scaled)

        test_pred_scaled = self.predict_scaled(x_test_scaled)
        test_pred = self.unscale_y(test_pred_scaled)
        self.evaluate(y_test, test_pred)

    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        error = y_pred - y_true
        self.rmse = float(np.sqrt(np.mean(error ** 2)))
        self.mae = float(np.mean(np.abs(error)))

        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
        self.r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

    def predict(
        self,
        property_type: str,
        area_m2: float,
        frontage_m: float,
        road_width_m: float,
        floors: float,
        bedrooms: float,
        rooms: float,
        district: str,
    ) -> PredictionResult:
        if property_type not in PROPERTY_TYPE_CODES:
            raise ValueError("Loại bất động sản không hợp lệ.")
        if district not in DISTRICTS:
            raise ValueError("Quận/huyện không hợp lệ.")

        x_new = np.array(
            [[
                PROPERTY_TYPE_CODES[property_type],
                area_m2,
                frontage_m,
                road_width_m,
                floors,
                bedrooms,
                rooms,
                DISTRICTS[district],
            ]],
            dtype=float,
        )
        price_scaled = self.predict_scaled(self.scale_x(x_new))
        price_million = max(float(self.unscale_y(price_scaled)[0]), 0.0)

        return PredictionResult(
            price_million_vnd=price_million,
            price_billion_vnd=price_million / 1000,
            price_per_m2_million=price_million / area_m2 if area_m2 else 0.0,
        )


_MODEL_CACHE: LinearRegressionModel | None = None
_MODEL_MTIME: float | None = None


def get_model(dataset_path: Path) -> LinearRegressionModel:
    global _MODEL_CACHE, _MODEL_MTIME

    dataset_path = Path(dataset_path)
    mtime = dataset_path.stat().st_mtime if dataset_path.exists() else None
    if _MODEL_CACHE is None or _MODEL_MTIME != mtime:
        _MODEL_CACHE = LinearRegressionModel(dataset_path)
        _MODEL_MTIME = mtime
    return _MODEL_CACHE
