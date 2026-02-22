import io
import pandas as pd
from datetime import datetime
from typing import Dict, List
from django.db import transaction
from fleet.models import Car
from .models import FuelRecord

REQUIRED_COLUMNS = ["plate_number", "date", "liters", "cost", "odometer"]


def _parse_row(row) -> Dict:
    errors: List[str] = []
    plate = str(row.get("plate_number")).strip()
    try:
        car = Car.objects.get(plate_number=plate)
    except Car.DoesNotExist:
        errors.append(f"Unknown plate_number: {plate}")
        car = None
    date_val = row.get("date")
    try:
        if isinstance(date_val, datetime):
            date = date_val.date()
        else:
            date = pd.to_datetime(date_val).date()
    except Exception:
        errors.append(f"Invalid date: {date_val}")
        date = None
    try:
        liters = float(row.get("liters"))
    except Exception:
        errors.append(f"Invalid liters: {row.get('liters')}")
        liters = None
    try:
        cost = float(row.get("cost"))
    except Exception:
        errors.append(f"Invalid cost: {row.get('cost')}")
        cost = None
    try:
        odometer = int(row.get("odometer"))
    except Exception:
        errors.append(f"Invalid odometer: {row.get('odometer')}")
        odometer = None
    return {
        "car": car,
        "date": date,
        "liters": liters,
        "cost": cost,
        "odometer": odometer,
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
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        summary["errors"].append(f"Missing columns: {', '.join(missing)}")
        return summary
    to_create = []
    for idx, row in df.iterrows():
        parsed = _parse_row(row)
        if parsed["errors"] or not all([parsed["car"], parsed["date"], parsed["liters"], parsed["cost"], parsed["odometer"]]):
            summary["errors"].append(f"Row {idx+1}: " + "; ".join(parsed["errors"]))
            continue
        record = FuelRecord(
            car=parsed["car"],
            date=parsed["date"],
            liters=parsed["liters"],
            cost=parsed["cost"],
            odometer=parsed["odometer"],
        )
        to_create.append(record)
    if not to_create:
        return summary
    try:
        with transaction.atomic():
            FuelRecord.objects.bulk_create(to_create, ignore_conflicts=True)
        summary["created"] = len(to_create)
    except Exception as e:
        summary["errors"].append(f"Bulk insert failed: {e}")
    return summary
