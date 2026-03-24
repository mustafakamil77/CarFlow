import io
import pandas as pd
from datetime import datetime
from typing import Dict, List
from django.db import transaction
from fleet.models import Car
from .models import FuelLog

REQUIRED_COLUMNS = ["plate_number", "liters", "price", "odometer"]


def _parse_row(row) -> Dict:
    errors: List[str] = []
    plate = str(row.get("plate_number")).strip()
    try:
        car = Car.objects.get(plate_number=plate)
    except Car.DoesNotExist:
        errors.append(f"Unknown plate_number: {plate}")
        car = None
    # FuelLog لا يحتوي حقلاً للتاريخ؛ نستخدم created_at تلقائياً
    try:
        liters = float(row.get("liters"))
    except Exception:
        errors.append(f"Invalid liters: {row.get('liters')}")
        liters = None
    # قبول price أو cost كاسم عمود للسعر
    price_val = row.get("price", row.get("cost"))
    try:
        price = float(price_val)
    except Exception:
        errors.append(f"Invalid price: {price_val}")
        price = None
    try:
        odometer = int(row.get("odometer"))
    except Exception:
        errors.append(f"Invalid odometer: {row.get('odometer')}")
        odometer = None
    return {
        "car": car,
        "liters": liters,
        "price": price,
        "odometer": odometer,
        "station": str(row.get("station")).strip() if "station" in row and row.get("station") is not None else "",
        "errors": errors,
    }


def process_excel(uploaded_file) -> Dict:
    summary = {"created": 0, "errors": []}
    try:
        content = uploaded_file.read()
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        summary["errors"].append(f"Failed to read Excel: {e}")
        return summary
    # دعم أعمدة قديمة: إذا كان 'cost' موجوداً ولم توجد 'price' نسمح بالمتابعة
    present = set(df.columns)
    missing = [c for c in REQUIRED_COLUMNS if c not in present and not (c == "price" and "cost" in present)]
    if missing:
        summary["errors"].append(f"Missing columns: {', '.join(missing)}")
        return summary
    to_create = []
    for idx, row in df.iterrows():
        parsed = _parse_row(row)
        if parsed["errors"] or not all([parsed["car"], parsed["liters"], parsed["price"], parsed["odometer"]]):
            summary["errors"].append(f"Row {idx+1}: " + "; ".join(parsed["errors"]))
            continue
        record = FuelLog(
            car=parsed["car"],
            liters=parsed["liters"],
            price=parsed["price"],
            odometer=parsed["odometer"],
            station=parsed["station"],
        )
        to_create.append(record)
    if not to_create:
        return summary
    try:
        with transaction.atomic():
            FuelLog.objects.bulk_create(to_create, ignore_conflicts=True)
        summary["created"] = len(to_create)
    except Exception as e:
        summary["errors"].append(f"Bulk insert failed: {e}")
    return summary
