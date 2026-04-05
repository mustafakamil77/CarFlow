from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import CarAssignment, CarEvent, CarEventImage, CarEventCondition


@transaction.atomic
def assign_driver_to_car(
    *,
    car,
    driver,
    start_odometer,
    notes="",
    scratches_notes="",
    cleanliness_notes="",
    fuel_level=None,
    images_by_caption=None,
    created_by=None,
):
    if car.status in {"inactive"}:
        raise ValidationError("Car is inactive.")
    if car.status in {"maintenance"}:
        raise ValidationError("Car is under maintenance.")
    open_assignment = car.assignments.filter(end_date__isnull=True).order_by("-start_date").first()
    if open_assignment:
        raise ValidationError("Car already has an open assignment.")

    now = timezone.now()
    assignment = CarAssignment.objects.create(
        car=car,
        driver=driver,
        start_date=now,
        start_odometer=start_odometer,
        notes=notes or "",
        created_by=created_by,
    )

    event = CarEvent.objects.create(
        car=car,
        event_type="handover",
        odometer=start_odometer,
        notes=notes or "",
        created_by=created_by,
    )

    CarEventCondition.objects.create(
        event=event,
        scratches_notes=scratches_notes or "",
        cleanliness_notes=cleanliness_notes or "",
        fuel_level=fuel_level,
    )

    if images_by_caption:
        for caption, image in images_by_caption.items():
            if image:
                CarEventImage.objects.create(event=event, image=image, caption=caption)

    car.status = "assigned"
    car.save(update_fields=["status"])

    if getattr(driver, "role", None) != "driver":
        driver.role = "driver"
        driver.save(update_fields=["role"])

    group, _ = Group.objects.get_or_create(name="Driver")
    if driver.user_id and not driver.user.groups.filter(id=group.id).exists():
        driver.user.groups.add(group)

    from accounts.models import DriverAssignment

    today = timezone.localdate()
    DriverAssignment.objects.filter(car=car, active=True).update(active=False, end_date=today)
    DriverAssignment.objects.create(
        driver=driver,
        car=car,
        region=car.region,
        start_date=today,
        end_date=None,
        active=True,
        notes=notes or "",
    )

    return assignment, event


@transaction.atomic
def return_car(
    *,
    car,
    end_odometer,
    notes="",
    scratches_notes="",
    cleanliness_notes="",
    fuel_level=None,
    images_by_caption=None,
    created_by=None,
):
    assignment = car.assignments.filter(end_date__isnull=True).order_by("-start_date").first()
    if not assignment:
        raise ValidationError("No open assignment for this car.")

    now = timezone.now()
    assignment.end_date = now
    assignment.end_odometer = end_odometer
    assignment.save(update_fields=["end_date", "end_odometer"])

    event = CarEvent.objects.create(
        car=car,
        event_type="return",
        odometer=end_odometer,
        notes=notes or "",
        created_by=created_by,
    )

    CarEventCondition.objects.create(
        event=event,
        scratches_notes=scratches_notes or "",
        cleanliness_notes=cleanliness_notes or "",
        fuel_level=fuel_level,
    )

    if images_by_caption:
        for caption, image in images_by_caption.items():
            if image:
                CarEventImage.objects.create(event=event, image=image, caption=caption)

    has_open_maintenance = car.maintenance_requests.exclude(status="completed").exists()
    car.status = "maintenance" if has_open_maintenance else "available"
    car.save(update_fields=["status"])

    from accounts.models import DriverAssignment

    today = timezone.localdate()
    DriverAssignment.objects.filter(car=car, active=True).update(active=False, end_date=today)

    return assignment, event


@transaction.atomic
def record_accident(
    *,
    car,
    notes="",
    liability_percent=None,
    images=None,
    created_by=None,
):
    event = CarEvent.objects.create(
        car=car,
        event_type="accident",
        notes=notes or "",
        created_by=created_by,
    )

    CarEventCondition.objects.create(
        event=event,
        liability_percent=liability_percent,
    )

    if images:
        for image in images:
            if image:
                CarEventImage.objects.create(event=event, image=image, caption="")

    return event
