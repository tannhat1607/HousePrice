from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "Avg. Area Income",                 # dien tich dat (m2)
    "Avg. Area House Age",              # so tang
    "Avg. Area Number of Rooms",        # so phong
    "Avg. Area Number of Bedrooms",     # so phong ngu
    "Area Population",                  # ma quan/huyen
]
TARGET_COLUMN = "Price"                 # gia dat, don vi trieu VND

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
    1. Truc quan hoa/tom tat du lieu
    2. Xay dung ham du doan: y_hat = X.w + b
    3. Xay dung ham mat mat: MSE
    4. Cap nhat weight va bias bang Gradient Descent
    5. Xay dung vong lap huan luyen
    6. Du doan du lieu moi
    """

    def __init__(self, dataset_path: Path, learning_rate: float = 0.03, epochs: int = 3000):
        self.dataset_path = Path(dataset_path)
        self.learning_rate = learning_rate
        self.epochs = epochs

        self.w: np.ndarray | None = None
        self.b: float = 0.0

        self.x_mean: np.ndarray | None = None
        self.x_std: np.ndarray | None = None
        self.y_mean: float = 0.0
        self.y_std: float = 1.0

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

        self.train()

    # ------------------------------------------------------------------
    # 1. Truc quan hoa/tom tat du lieu
    # ------------------------------------------------------------------
    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(self.dataset_path)

        for col in FEATURE_COLUMNS + [TARGET_COLUMN]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN, "Address"])

        # Loai bo dong bat thuong de model hoc on dinh hon.
        df = df[
            (df["Avg. Area Income"].between(20, 5000))
            & (df["Avg. Area House Age"].between(0, 20))
            & (df["Avg. Area Number of Rooms"].between(1, 20))
            & (df["Avg. Area Number of Bedrooms"].between(0, 15))
            & (df["Area Population"].between(1, 7))
            & (df[TARGET_COLUMN].between(100, 200000))
        ].copy()

        if len(df) < 20:
            raise ValueError("Dataset qua it dong hop le de train model.")

        return df

    def summarize_data(self, df: pd.DataFrame) -> None:
        self.row_count = len(df)
        self.district_counts = df["Address"].value_counts().to_dict()
        self.avg_price_by_district = df.groupby("Address")[TARGET_COLUMN].mean().round(2).to_dict()
        self.avg_area_by_district = df.groupby("Address")["Avg. Area Income"].mean().round(2).to_dict()

    def chart_data(self) -> dict:
        labels = list(DISTRICTS.keys())
        return {
            "labels": labels,
            "counts": [int(self.district_counts.get(label, 0)) for label in labels],
            "avg_prices": [float(self.avg_price_by_district.get(label, 0)) for label in labels],
            "avg_areas": [float(self.avg_area_by_district.get(label, 0)) for label in labels],
        }

    # ------------------------------------------------------------------
    # Chuan bi X, y va chuan hoa du lieu
    # ------------------------------------------------------------------
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
        index = rng.permutation(len(x))
        split = int(len(index) * (1 - test_size))
        train_index = index[:split]
        test_index = index[split:]
        return x[train_index], x[test_index], y[train_index], y[test_index]

    def fit_scaler(self, x_train: np.ndarray, y_train: np.ndarray) -> None:
        self.x_mean = x_train.mean(axis=0)
        self.x_std = x_train.std(axis=0)
        self.x_std[self.x_std == 0] = 1.0

        # Train tren log(price) de giam anh huong outlier gia dat.
        y_log = np.log1p(y_train)
        self.y_mean = float(y_log.mean())
        self.y_std = float(y_log.std()) or 1.0

    def scale_x(self, x: np.ndarray) -> np.ndarray:
        if self.x_mean is None or self.x_std is None:
            raise RuntimeError("Chua fit scaler cho X.")
        return (x - self.x_mean) / self.x_std

    def scale_y(self, y: np.ndarray) -> np.ndarray:
        y_log = np.log1p(y)
        return (y_log - self.y_mean) / self.y_std

    def unscale_y(self, y_scaled: np.ndarray) -> np.ndarray:
        y_log = y_scaled * self.y_std + self.y_mean
        return np.expm1(y_log)

    # ------------------------------------------------------------------
    # 2. Xay dung ham du doan
    # ------------------------------------------------------------------
    def predict_scaled(self, x: np.ndarray) -> np.ndarray:
        if self.w is None:
            raise RuntimeError("Model chua duoc tao.")
        return x @ self.w + self.b

    # ------------------------------------------------------------------
    # 3. Xay dung ham mat mat MSE
    # ------------------------------------------------------------------
    def loss(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean((y_pred - y_true) ** 2))

    # ------------------------------------------------------------------
    # 4. Cap nhat weight va bias
    # ------------------------------------------------------------------
    def update_weights(self, x: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        if self.w is None:
            raise RuntimeError("Model chua duoc tao.")

        n = len(y_true)
        error = y_pred - y_true
        dw = (2 / n) * (x.T @ error)
        db = float((2 / n) * np.sum(error))

        self.w -= self.learning_rate * dw
        self.b -= self.learning_rate * db

    # ------------------------------------------------------------------
    # 5. Xay dung mo hinh huan luyen
    # ------------------------------------------------------------------
    def train(self) -> None:
        df = self.load_data()
        self.summarize_data(df)

        x, y = self.select_x_y(df)
        x_train, x_test, y_train, y_test = self.split_train_test(x, y)
        self.train_count = len(x_train)
        self.test_count = len(x_test)

        self.fit_scaler(x_train, y_train)
        x_train = self.scale_x(x_train)
        x_test = self.scale_x(x_test)
        y_train = self.scale_y(y_train)

        self.w = np.zeros(x_train.shape[1], dtype=float)
        self.b = 0.0
        self.loss_history = []

        for _ in range(self.epochs):
            y_pred = self.predict_scaled(x_train)
            current_loss = self.loss(y_train, y_pred)
            self.loss_history.append(current_loss)
            self.update_weights(x_train, y_train, y_pred)

        test_pred_scaled = self.predict_scaled(x_test)
        test_pred = self.unscale_y(test_pred_scaled)
        self.evaluate(y_test, test_pred)

    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> None:
        error = y_pred - y_true
        self.rmse = float(np.sqrt(np.mean(error ** 2)))
        self.mae = float(np.mean(np.abs(error)))

        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
        self.r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

    # ------------------------------------------------------------------
    # 6. Du doan du lieu moi
    # ------------------------------------------------------------------
    def predict(
        self,
        area_m2: float,
        floors: float,
        rooms: float,
        bedrooms: float,
        district: str,
    ) -> PredictionResult:
        district_code = DISTRICTS[district]
        x_new = np.array([[area_m2, floors, rooms, bedrooms, district_code]], dtype=float)
        x_new = self.scale_x(x_new)

        price_scaled = self.predict_scaled(x_new)
        price_million = float(self.unscale_y(price_scaled)[0])
        price_million = max(price_million, 0.0)

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
