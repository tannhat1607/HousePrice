from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


TARGET = "price_million_vnd"
PRICE_PER_M2 = "price_per_m2_million"

# Cac feature dau vao cua model du doan gia dat.
# Khong dung area_x_frontage vi feature nay tuong quan manh voi area/frontage,
# co the lam Linear Regression hoc he so mat tien nguoc dau.
FEATURES = ["area_m2", "frontage_m", "road_width_m", "district_code"]

DISTRICTS = {
    "Hai Chau": 1,
    "Thanh Khe": 2,
    "Son Tra": 3,
    "Ngu Hanh Son": 4,
    "Lien Chieu": 5,
    "Cam Le": 6,
    "Hoa Vang": 7,
}

DISTRICT_LABELS = {
    "Hai Chau": "Hải Châu",
    "Thanh Khe": "Thanh Khê",
    "Son Tra": "Sơn Trà",
    "Ngu Hanh Son": "Ngũ Hành Sơn",
    "Lien Chieu": "Liên Chiểu",
    "Cam Le": "Cẩm Lệ",
    "Hoa Vang": "Hòa Vang",
}


@dataclass
class PredictionResult:
    price_million_vnd: float
    price_billion_vnd: float
    price_per_m2_million: float
    algorithm: str


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
    mse = np.mean(error ** 2)
    rmse = np.sqrt(np.mean(error ** 2))
    ss_res = np.sum(error ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    return mae, mse, rmse, r2


class LinearRegressionModel:
    def __init__(self, dataset_path: Path):
        self.dataset_path = Path(dataset_path)
        self.df = load_land_data(self.dataset_path)

        # Tao X, y tu dataset da loc. y la don gia trieu/m2.
        X = np.nan_to_num(self.df[FEATURES].values, nan=0)
        y = np.nan_to_num(self.df[PRICE_PER_M2].values, nan=0)

        self.train_indexes, self.test_indexes = self.get_train_test_indexes(len(self.df))
        self.test_area_values = self.df.iloc[self.test_indexes]["area_m2"].to_numpy(dtype=float)
        self.y_test_unit = y[self.test_indexes]
        self.y_test_total = y[self.test_indexes] * self.test_area_values

        linear_pred_total = self.train_linear_regression(X, y)
        rf_pred_total = self.train_random_forest(X, y)
        self.choose_best_model(linear_pred_total, rf_pred_total)

        primary_result = self.linear_result
        self.primary_model_key = "linear"
        self.primary_algorithm = primary_result["name"]
        self.mae = primary_result["mae"]
        self.mse = primary_result["mse"]
        self.rmse = primary_result["rmse"]
        self.r2 = primary_result["r2"]
        self.mae_billion = self.mae / 1000
        self.rmse_billion = self.rmse / 1000
        self.mse_billion2 = self.mse / 1_000_000
        self.row_count = len(self.df)
        self.train_count = len(self.train_indexes)
        self.test_count = len(self.test_indexes)
        self.feature_count = len(FEATURES)
        self.feature_names = FEATURES
        self.actual_predicted_points = self.make_actual_predicted_points(self.y_test_unit, self.linear_pred_unit)
        self.loss_points = self.make_loss_points()
        self.heatmap_points, self.heatmap_labels = self.make_correlation_heatmap()

        # Du lieu thong ke phuc vu bieu do tren giao dien.
        self.district_counts = self.df["district"].value_counts().to_dict()
        self.avg_price_by_district = self.df.groupby("district")[PRICE_PER_M2].mean().round(2).to_dict()
        self.avg_area_by_district = self.df.groupby("district")["area_m2"].mean().round(2).to_dict()
        self.scatter_points, self.regression_line_points = self.make_regression_chart()

    # =====================
    # Linear Regression
    # =====================

    def train_linear_regression(self, X, y):
        X_train = X[self.train_indexes]
        X_test = X[self.test_indexes]
        y_train_raw = y[self.train_indexes]
        y_test_raw = y[self.test_indexes]

        X_train, X_test, self.X_mean, self.X_std = normalize_train_test(X_train, X_test)
        y_train, y_test, self.y_mean, self.y_std = normalize_train_test(y_train_raw, y_test_raw)

        X_train = add_bias(X_train)
        X_test = add_bias(X_test)

        self.weights, self.train_history, self.test_history = train(X_train, y_train, X_test, y_test)

        pred_unit = predict(X_test, self.weights) * self.y_std + self.y_mean
        self.linear_pred_unit = pred_unit
        pred_total = pred_unit * self.test_area_values
        mae, mse, rmse, r2 = metrics(self.y_test_total, pred_total)
        self.linear_result = self.format_model_result("Linear Regression", mae, mse, rmse, r2)
        return pred_total

    def predict_linear(self, X_new):
        X_new = (X_new - self.X_mean) / self.X_std
        X_new = add_bias(X_new)
        return float(predict(X_new, self.weights)[0] * self.y_std + self.y_mean)

    # =====================
    # Random Forest
    # =====================

    def train_random_forest(self, X, y):
        self.random_forest = RandomForestRegressor(
            n_estimators=400,
            max_depth=6,
            min_samples_leaf=10,
            random_state=42,
        )
        self.random_forest.fit(X[self.train_indexes], y[self.train_indexes])

        pred_unit = self.random_forest.predict(X[self.test_indexes])
        self.random_forest_pred_unit = pred_unit
        pred_total = pred_unit * self.test_area_values
        mae, mse, rmse, r2 = metrics(self.y_test_total, pred_total)
        self.random_forest_result = self.format_model_result("Random Forest", mae, mse, rmse, r2)
        return pred_total

    def predict_random_forest(self, X_new):
        return float(self.random_forest.predict(X_new)[0])

    # =====================
    # Model comparison
    # =====================

    def choose_best_model(self, linear_pred_total, rf_pred_total):
        self.model_results = {
            "linear": self.linear_result,
            "random_forest": self.random_forest_result,
        }
        self.best_model_key = (
            "random_forest"
            if self.random_forest_result["r2"] > self.linear_result["r2"]
            else "linear"
        )
        self.best_algorithm = self.model_results[self.best_model_key]["name"]

    def format_model_result(self, name, mae, mse, rmse, r2):
        return {
            "name": name,
            "mae": float(mae),
            "mse": float(mse),
            "rmse": float(rmse),
            "r2": float(r2),
            "mae_billion": float(mae / 1000),
            "mse_billion2": float(mse / 1_000_000),
            "rmse_billion": float(rmse / 1000),
        }

    def make_actual_predicted_points(self, y_true, y_pred):
        points = [
            {"x": round(float(actual), 2), "y": round(float(predicted), 2)}
            for actual, predicted in zip(y_true, y_pred)
        ]
        return points[:250]

    def make_loss_points(self):
        if not self.train_history:
            return {"train": [], "test": []}

        step = max(len(self.train_history) // 120, 1)
        epochs = list(range(0, len(self.train_history), step))
        return {
            "train": [
                {"x": int(epoch), "y": round(float(self.train_history[epoch]), 6)}
                for epoch in epochs
            ],
            "test": [
                {"x": int(epoch), "y": round(float(self.test_history[epoch]), 6)}
                for epoch in epochs
            ],
        }

    def make_correlation_heatmap(self):
        columns = FEATURES + [PRICE_PER_M2]
        labels = ["Diện tích", "Mặt tiền", "Đường", "Khu vực", "Đơn giá"]
        corr = self.df[columns].corr(numeric_only=True).fillna(0)
        points = []
        for row_index, row_name in enumerate(columns):
            for col_index, col_name in enumerate(columns):
                points.append({
                    "x": labels[col_index],
                    "y": labels[row_index],
                    "v": round(float(corr.loc[row_name, col_name]), 3),
                })
        return points, labels

    def make_regression_chart(self):
        # Bieu do minh hoa moi quan he dien tich - don gia dat.
        # Model chinh van dung nhieu feature, duong nay chi de truc quan hoa.
        chart_df = self.df[["area_m2", PRICE_PER_M2]].dropna().copy()
        chart_df = chart_df[
            (chart_df["area_m2"] <= chart_df["area_m2"].quantile(0.98))
            & (chart_df[PRICE_PER_M2] <= chart_df[PRICE_PER_M2].quantile(0.98))
        ]

        if len(chart_df) > 350:
            chart_df = chart_df.sample(350, random_state=42)

        scatter_points = [
            {"x": round(float(row.area_m2), 2), "y": round(float(row.price_per_m2_million), 2)}
            for row in chart_df.itertuples(index=False)
        ]

        x = chart_df["area_m2"].to_numpy(dtype=float)
        y = chart_df[PRICE_PER_M2].to_numpy(dtype=float)
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

    def get_train_test_indexes(self, n_rows: int):
        np.random.seed(42)
        indices = np.arange(n_rows)
        np.random.shuffle(indices)
        test_size = int(0.2 * len(indices))
        return indices[test_size:], indices[:test_size]

    def chart_data(self):
        # Tra ve JSON-friendly data cho Chart.js o frontend.
        labels = list(DISTRICTS.keys())
        return {
            "labels": [DISTRICT_LABELS[label] for label in labels],
            "counts": [int(self.district_counts.get(label, 0)) for label in labels],
            "avg_prices": [float(self.avg_price_by_district.get(label, 0)) for label in labels],
            "avg_areas": [float(self.avg_area_by_district.get(label, 0)) for label in labels],
            "scatter_points": self.scatter_points,
            "regression_line": self.regression_line_points,
            "loss": self.loss_points,
            "actual_predicted": self.actual_predicted_points,
            "heatmap_points": self.heatmap_points,
            "heatmap_labels": self.heatmap_labels,
        }

    def predict(
        self,
        area_m2: float,
        frontage_m: float,
        road_width_m: float,
        district: str,
        algorithm: str = "linear",
    ) -> PredictionResult:
        if district not in DISTRICTS:
            raise ValueError("Quận/huyện không hợp lệ.")

        # Tao 1 dong du lieu moi dung cung thu tu FEATURES luc train.
        X_new = np.array([[area_m2, frontage_m, road_width_m, DISTRICTS[district]]], dtype=float)

        if algorithm == "best":
            algorithm = self.primary_model_key
        if algorithm not in self.model_results:
            raise ValueError("Thuật toán không hợp lệ.")

        if algorithm == "random_forest":
            price_per_m2 = self.predict_random_forest(X_new)
        else:
            price_per_m2 = self.predict_linear(X_new)

        price_per_m2 = max(price_per_m2, 0)
        price_million = price_per_m2 * area_m2
        price_million = max(price_million, 0)

        return PredictionResult(
            price_million_vnd=price_million,
            price_billion_vnd=price_million / 1000,
            price_per_m2_million=price_per_m2,
            algorithm=self.model_results[algorithm]["name"],
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
