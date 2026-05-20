from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse

from .ml import DISTRICTS, PROPERTY_TYPES, get_model


DEFAULT_INPUTS = {
    "property_type": "land",
    "area_m2": 100,
    "frontage_m": 5,
    "road_width_m": 7.5,
    "floors": 0,
    "rooms": 0,
    "bedrooms": 0,
    "district": "Cam Le",
}


def index(request):
    inputs = DEFAULT_INPUTS.copy()
    result = None
    error = None

    try:
        model = get_model(settings.DATASET_PATH)
    except Exception as exc:
        model = None
        error = str(exc)

    if request.method == "POST":
        query = urlencode({
            "property_type": request.POST.get("property_type", DEFAULT_INPUTS["property_type"]),
            "area_m2": request.POST.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "frontage_m": request.POST.get("frontage_m", DEFAULT_INPUTS["frontage_m"]),
            "road_width_m": request.POST.get("road_width_m", DEFAULT_INPUTS["road_width_m"]),
            "floors": request.POST.get("floors", DEFAULT_INPUTS["floors"]),
            "rooms": request.POST.get("rooms", DEFAULT_INPUTS["rooms"]),
            "bedrooms": request.POST.get("bedrooms", DEFAULT_INPUTS["bedrooms"]),
            "district": request.POST.get("district", DEFAULT_INPUTS["district"]),
            "predict": "1",
        })
        return redirect(f"{reverse('predictor:index')}?{query}#result-section")

    if request.GET:
        inputs = {
            key: request.GET.get(key, value)
            for key, value in DEFAULT_INPUTS.items()
        }

    if request.GET.get("predict") == "1" and model:
        try:
            inputs = {
                "property_type": request.GET.get("property_type", DEFAULT_INPUTS["property_type"]),
                "area_m2": float(request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"])),
                "frontage_m": float(request.GET.get("frontage_m", DEFAULT_INPUTS["frontage_m"])),
                "road_width_m": float(request.GET.get("road_width_m", DEFAULT_INPUTS["road_width_m"])),
                "floors": int(float(request.GET.get("floors", DEFAULT_INPUTS["floors"]))),
                "rooms": int(float(request.GET.get("rooms", DEFAULT_INPUTS["rooms"]))),
                "bedrooms": int(float(request.GET.get("bedrooms", DEFAULT_INPUTS["bedrooms"]))),
                "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
            }

            if inputs["property_type"] not in PROPERTY_TYPES:
                raise ValueError("Loại bất động sản không hợp lệ.")
            if inputs["district"] not in DISTRICTS:
                raise ValueError("Quận/huyện không hợp lệ.")
            if inputs["area_m2"] <= 0:
                raise ValueError("Diện tích phải lớn hơn 0.")
            if inputs["frontage_m"] < 0 or inputs["road_width_m"] < 0:
                raise ValueError("Mặt tiền và đường trước nhà không được âm.")

            result = model.predict(**inputs)
        except Exception as exc:
            error = str(exc)

    context = {
        "property_types": PROPERTY_TYPES,
        "selected_property_type_label": PROPERTY_TYPES.get(inputs.get("property_type"), ""),
        "districts": DISTRICTS.keys(),
        "inputs": inputs,
        "result": result,
        "error": error,
        "model": model,
        "chart_data": model.chart_data() if model else {},
    }
    return render(request, "index.html", context)
