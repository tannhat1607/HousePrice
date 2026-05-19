from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse

from .ml import DISTRICTS, get_model


DEFAULT_INPUTS = {
    "area_m2": 100,
    "floors": 1,
    "rooms": 4,
    "bedrooms": 2,
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
            "area_m2": request.POST.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "floors": request.POST.get("floors", DEFAULT_INPUTS["floors"]),
            "rooms": request.POST.get("rooms", DEFAULT_INPUTS["rooms"]),
            "bedrooms": request.POST.get("bedrooms", DEFAULT_INPUTS["bedrooms"]),
            "district": request.POST.get("district", DEFAULT_INPUTS["district"]),
            "predict": "1",
        })
        return redirect(f"{reverse('predictor:index')}?{query}#result-section")

    if request.GET:
        inputs = {
            "area_m2": request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"]),
            "floors": request.GET.get("floors", DEFAULT_INPUTS["floors"]),
            "rooms": request.GET.get("rooms", DEFAULT_INPUTS["rooms"]),
            "bedrooms": request.GET.get("bedrooms", DEFAULT_INPUTS["bedrooms"]),
            "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
        }

    if request.GET.get("predict") == "1" and model:
        try:
            inputs = {
                "area_m2": float(request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"])),
                "floors": float(request.GET.get("floors", DEFAULT_INPUTS["floors"])),
                "rooms": float(request.GET.get("rooms", DEFAULT_INPUTS["rooms"])),
                "bedrooms": float(request.GET.get("bedrooms", DEFAULT_INPUTS["bedrooms"])),
                "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
            }

            if inputs["district"] not in DISTRICTS:
                raise ValueError("Quận không hợp lệ.")
            if inputs["area_m2"] <= 0:
                raise ValueError("Diện tích phải lớn hơn 0.")

            result = model.predict(**inputs)
        except Exception as exc:
            error = str(exc)

    context = {
        "districts": DISTRICTS.keys(),
        "inputs": inputs,
        "result": result,
        "error": error,
        "model": model,
        "chart_data": model.chart_data() if model else {},
    }
    return render(request, "index.html", context)
