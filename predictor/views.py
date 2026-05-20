from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse

from .ml import DISTRICTS, get_model


DEFAULT_INPUTS = {
    "area_m2": 100,
    "frontage_m": 5,
    "road_width_m": 7.5,
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
            "frontage_m": request.POST.get("frontage_m", DEFAULT_INPUTS["frontage_m"]),
            "road_width_m": request.POST.get("road_width_m", DEFAULT_INPUTS["road_width_m"]),
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
                "area_m2": float(request.GET.get("area_m2", DEFAULT_INPUTS["area_m2"])),
                "frontage_m": float(request.GET.get("frontage_m", DEFAULT_INPUTS["frontage_m"])),
                "road_width_m": float(request.GET.get("road_width_m", DEFAULT_INPUTS["road_width_m"])),
                "district": request.GET.get("district", DEFAULT_INPUTS["district"]),
            }

            if inputs["district"] not in DISTRICTS:
                raise ValueError("Quan/huyen khong hop le.")
            if inputs["area_m2"] <= 0:
                raise ValueError("Dien tich phai lon hon 0.")
            if inputs["frontage_m"] < 0 or inputs["road_width_m"] < 0:
                raise ValueError("Mat tien va duong truoc dat khong duoc am.")

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
