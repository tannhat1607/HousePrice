from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse

from .ml import DISTRICT_LABELS, DISTRICTS, get_model


DEFAULT_INPUTS = {
    "area_m2": 100,
    "frontage_m": 5,
    "road_width_m": 7.5,
    "district": "Cam Le",
    "algorithm": "linear",
}


def load_model():
    return get_model(settings.DATASET_PATH)


def index(request):
    error = None
    try:
        model = load_model()
    except Exception as exc:
        model = None
        error = str(exc)

    context = {
        "page": "home",
        "model": model,
        "error": error,
    }
    return render(request, "index.html", context)


def linear(request):
    inputs = DEFAULT_INPUTS.copy()
    result = None
    error = None

    try:
        model = load_model()
    except Exception as exc:
        model = None
        error = str(exc)

    if request.method == "POST":
        query = urlencode({
            "area_m2": request.POST.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "frontage_m": request.POST.get("frontage_m", DEFAULT_INPUTS["frontage_m"]),
            "road_width_m": request.POST.get("road_width_m", DEFAULT_INPUTS["road_width_m"]),
            "district": request.POST.get("district", DEFAULT_INPUTS["district"]),
            "algorithm": DEFAULT_INPUTS["algorithm"],
            "predict": "1",
        })
        return redirect(f"{reverse('predictor:linear')}?{query}#result-section")

    if request.GET:
        inputs = {
            key: request.GET.get(key, value)
            for key, value in DEFAULT_INPUTS.items()
        }
        inputs["algorithm"] = DEFAULT_INPUTS["algorithm"]
    elif request.session.get("last_linear_prediction"):
        last_prediction = request.session["last_linear_prediction"]
        inputs = last_prediction["inputs"]
        result = last_prediction["result"]

    if request.GET.get("predict") == "1" and model:
        try:
            inputs = {
                "area_m2": float(request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"])),
                "frontage_m": float(request.GET.get("frontage_m", DEFAULT_INPUTS["frontage_m"])),
                "road_width_m": float(request.GET.get("road_width_m", DEFAULT_INPUTS["road_width_m"])),
                "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
                "algorithm": DEFAULT_INPUTS["algorithm"],
            }

            if inputs["district"] not in DISTRICTS:
                raise ValueError("Quận/huyện không hợp lệ.")
            if inputs["algorithm"] not in model.model_results:
                raise ValueError("Thuật toán không hợp lệ.")
            if inputs["area_m2"] <= 0:
                raise ValueError("Diện tích phải lớn hơn 0.")
            if inputs["frontage_m"] < 0 or inputs["road_width_m"] < 0:
                raise ValueError("Mặt tiền và đường trước đất không được âm.")

            result = model.predict(**inputs)
            request.session["last_linear_prediction"] = {
                "inputs": inputs,
                "result": prediction_to_dict(result),
            }
            save_recent_prediction(request, inputs, result)
        except Exception as exc:
            error = str(exc)

    context = {
        "page": "linear",
        "districts": DISTRICT_LABELS.items(),
        "selected_district_label": DISTRICT_LABELS.get(inputs.get("district"), inputs.get("district")),
        "inputs": inputs,
        "algorithms": model.model_results.items() if model else [],
        "result": result,
        "error": error,
        "model": model,
        "recent_predictions": request.session.get("recent_predictions", []),
    }
    return render(request, "linear.html", context)


def analytics(request):
    error = None
    rf_error = None
    rf_result = None
    rf_inputs = DEFAULT_INPUTS.copy()
    rf_inputs["algorithm"] = "random_forest"

    try:
        model = load_model()
    except Exception as exc:
        model = None
        error = str(exc)

    if request.method == "POST":
        query = urlencode({
            "area_m2": request.POST.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "frontage_m": request.POST.get("frontage_m", DEFAULT_INPUTS["frontage_m"]),
            "road_width_m": request.POST.get("road_width_m", DEFAULT_INPUTS["road_width_m"]),
            "district": request.POST.get("district", DEFAULT_INPUTS["district"]),
            "rf_predict": "1",
        })
        return redirect(f"{reverse('predictor:analytics')}?{query}#random-forest-form")

    if request.GET:
        rf_inputs = {
            "area_m2": request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "frontage_m": request.GET.get("frontage_m", DEFAULT_INPUTS["frontage_m"]),
            "road_width_m": request.GET.get("road_width_m", DEFAULT_INPUTS["road_width_m"]),
            "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
            "algorithm": "random_forest",
        }
    elif request.session.get("last_random_forest_prediction"):
        last_prediction = request.session["last_random_forest_prediction"]
        rf_inputs = last_prediction["inputs"]
        rf_result = last_prediction["result"]

    if request.GET.get("rf_predict") == "1" and model:
        try:
            rf_inputs = {
                "area_m2": float(request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"])),
                "frontage_m": float(request.GET.get("frontage_m", DEFAULT_INPUTS["frontage_m"])),
                "road_width_m": float(request.GET.get("road_width_m", DEFAULT_INPUTS["road_width_m"])),
                "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
                "algorithm": "random_forest",
            }

            if rf_inputs["district"] not in DISTRICTS:
                raise ValueError("Quận/huyện không hợp lệ.")
            if rf_inputs["area_m2"] <= 0:
                raise ValueError("Diện tích phải lớn hơn 0.")
            if rf_inputs["frontage_m"] < 0 or rf_inputs["road_width_m"] < 0:
                raise ValueError("Mặt tiền và đường trước đất không được âm.")

            rf_result = model.predict(**rf_inputs)
            request.session["last_random_forest_prediction"] = {
                "inputs": rf_inputs,
                "result": prediction_to_dict(rf_result),
            }
        except Exception as exc:
            rf_error = str(exc)

    context = {
        "page": "analytics",
        "model": model,
        "error": error,
        "rf_error": rf_error,
        "rf_result": rf_result,
        "rf_inputs": rf_inputs,
        "districts": DISTRICT_LABELS.items(),
        "rf_selected_district_label": DISTRICT_LABELS.get(
            rf_inputs.get("district"),
            rf_inputs.get("district"),
        ),
        "chart_data": model.chart_data() if model else {},
    }
    return render(request, "analytics.html", context)


def save_recent_prediction(request, inputs, result):
    recent = request.session.get("recent_predictions", [])
    recent.insert(0, {
        "area_m2": round(float(inputs["area_m2"]), 1),
        "frontage_m": round(float(inputs["frontage_m"]), 1),
        "road_width_m": round(float(inputs["road_width_m"]), 1),
        "district": DISTRICT_LABELS.get(inputs["district"], inputs["district"]),
        "algorithm": result.algorithm,
        "price_billion_vnd": round(result.price_billion_vnd, 2),
    })
    request.session["recent_predictions"] = recent[:8]


def prediction_to_dict(result):
    return {
        "price_million_vnd": result.price_million_vnd,
        "price_billion_vnd": result.price_billion_vnd,
        "price_per_m2_million": result.price_per_m2_million,
        "algorithm": result.algorithm,
    }
