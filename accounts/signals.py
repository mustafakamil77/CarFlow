import io
import uuid

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models.fields.files import ImageField
from django.db.models.signals import post_delete, post_migrate, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from PIL import Image

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    register_heif_opener = None


DEFAULT_IMAGE_OPTIMIZATION = {
    "enabled": True,
    "max_upload_bytes": 5 * 1024 * 1024,
    "max_side_px": 1000,
    "target_bytes": 100 * 1024,
    "output_format": "WEBP",
    "min_quality": 35,
    "max_quality": 85,
    "max_iterations": 7,
    "webp_method": 6,
    "exclude_fields": [],
}

_validators_attached = False


def ensure_role_groups():
    roles = ["Admin", "Manager", "Driver"]
    for name in roles:
        Group.objects.get_or_create(name=name)


@receiver(post_migrate)
def create_groups(sender, **kwargs):
    ensure_role_groups()


def _get_image_optimization_settings():
    cfg = dict(DEFAULT_IMAGE_OPTIMIZATION)
    user_cfg = getattr(settings, "CARFLOW_IMAGE_OPTIMIZATION", None) or {}
    cfg.update({k: v for k, v in user_cfg.items() if v is not None})
    cfg["exclude_fields"] = set(cfg.get("exclude_fields") or [])
    return cfg


def _validate_max_upload_size(uploaded_file, *, max_upload_bytes: int):
    size = getattr(uploaded_file, "size", None)
    if size is None:
        return
    if int(size) > int(max_upload_bytes):
        raise ValidationError(f"حجم الملف كبير جداً. الحد الأقصى {max_upload_bytes // (1024 * 1024)}MB.")


def _build_optimized_path(*, sender, field_name: str, output_ext: str):
    now = timezone.now()
    return (
        f"uploads/optimized/{sender._meta.app_label}/{sender._meta.model_name}/"
        f"{field_name}/{now:%Y/%m}/{uuid.uuid4().hex}.{output_ext}"
    )


def _open_image(file_obj):
    try:
        file_obj.seek(0)
    except Exception:
        pass
    try:
        return Image.open(file_obj)
    except Exception:
        name = str(getattr(file_obj, "name", "") or "").lower()
        if name.endswith((".heic", ".heif")) and register_heif_opener is None:
            raise ValidationError("صيغة HEIC/HEIF تحتاج تثبيت pillow-heif على الخادم.")
        raise ValidationError("الملف المرفوع ليس صورة صالحة أو غير مدعوم.")


def _normalize_image(img: Image.Image):
    try:
        img = img.copy()
    except Exception:
        pass
    if img.mode in {"RGBA", "LA"}:
        return img.convert("RGBA")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _resize_image(img: Image.Image, *, max_side_px: int):
    w, h = img.size
    if max(w, h) <= max_side_px:
        return img
    img.thumbnail((max_side_px, max_side_px), Image.Resampling.LANCZOS)
    return img


def _encode_webp_target(img: Image.Image, *, target_bytes: int, min_quality: int, max_quality: int, max_iterations: int, webp_method: int):
    def render(q: int):
        buf = io.BytesIO()
        img.save(
            buf,
            format="WEBP",
            quality=int(q),
            method=int(webp_method),
            optimize=True,
        )
        return buf.getvalue()

    hi = int(max_quality)
    lo = int(min_quality)

    best = render(hi)
    if len(best) <= target_bytes:
        return best

    best_under = None
    for _ in range(max_iterations):
        if lo > hi:
            break
        mid = (lo + hi) // 2
        data = render(mid)
        if len(data) <= target_bytes:
            best_under = data
            lo = mid + 1
        else:
            hi = mid - 1

    if best_under is not None:
        return best_under
    return render(min_quality)


def _optimize_uploaded_image(uploaded_file, *, sender, field_name: str, cfg: dict):
    _validate_max_upload_size(uploaded_file, max_upload_bytes=cfg["max_upload_bytes"])
    img = _open_image(uploaded_file)
    img = _normalize_image(img)
    img = _resize_image(img, max_side_px=int(cfg["max_side_px"]))
    data = _encode_webp_target(
        img,
        target_bytes=int(cfg["target_bytes"]),
        min_quality=int(cfg["min_quality"]),
        max_quality=int(cfg["max_quality"]),
        max_iterations=int(cfg["max_iterations"]),
        webp_method=int(cfg["webp_method"]),
    )
    name = _build_optimized_path(sender=sender, field_name=field_name, output_ext="webp")
    return name, data


def _attach_image_validators_once():
    global _validators_attached
    if _validators_attached:
        return
    cfg = _get_image_optimization_settings()
    max_upload_bytes = int(cfg["max_upload_bytes"])

    def _validator(uploaded_file):
        _validate_max_upload_size(uploaded_file, max_upload_bytes=max_upload_bytes)

    for model in apps.get_models():
        for field in model._meta.fields:
            if isinstance(field, ImageField) and _validator not in field.validators:
                field.validators.append(_validator)
    _validators_attached = True


@receiver(pre_save)
def optimize_all_images_before_save(sender, instance, **kwargs):
    if not getattr(sender, "_meta", None) or sender._meta.abstract or sender._meta.proxy:
        return
    cfg = _get_image_optimization_settings()
    if not cfg.get("enabled", True):
        return

    _attach_image_validators_once()

    processed = getattr(instance, "_carflow_processed_images", None)
    if processed is None:
        processed = set()
        setattr(instance, "_carflow_processed_images", processed)

    pending_delete = getattr(instance, "_carflow_pending_image_deletes", None)
    if pending_delete is None:
        pending_delete = []
        setattr(instance, "_carflow_pending_image_deletes", pending_delete)

    for field in sender._meta.fields:
        if not isinstance(field, ImageField):
            continue
        full_key = f"{sender._meta.label}.{field.name}"
        if full_key in cfg["exclude_fields"]:
            continue
        if field.name in processed:
            continue
        ff = getattr(instance, field.name, None)
        if not ff:
            continue
        if getattr(ff, "_committed", True):
            continue
        file_obj = getattr(ff, "file", None)
        if not file_obj:
            continue
        if getattr(file_obj, "_carflow_optimized", False):
            processed.add(field.name)
            continue

        old_name = None
        if instance.pk:
            try:
                old_name = sender.objects.filter(pk=instance.pk).values_list(field.name, flat=True).first()
            except Exception:
                old_name = None

        new_name, data = _optimize_uploaded_image(file_obj, sender=sender, field_name=field.name, cfg=cfg)
        ff.save(new_name, ContentFile(data), save=False)
        try:
            ff.file._carflow_optimized = True
        except Exception:
            pass
        processed.add(field.name)

        if old_name and old_name != ff.name:
            pending_delete.append((field.name, old_name))


@receiver(post_save)
def cleanup_replaced_images_after_save(sender, instance, **kwargs):
    pending_delete = getattr(instance, "_carflow_pending_image_deletes", None) or []
    if not pending_delete:
        return
    for field_name, old_name in pending_delete:
        try:
            field = sender._meta.get_field(field_name)
            storage = field.storage
            if old_name and storage.exists(old_name):
                storage.delete(old_name)
        except Exception:
            pass
    setattr(instance, "_carflow_pending_image_deletes", [])


@receiver(post_delete)
def cleanup_images_on_delete(sender, instance, **kwargs):
    if not getattr(sender, "_meta", None) or sender._meta.abstract or sender._meta.proxy:
        return
    for field in sender._meta.fields:
        if not isinstance(field, ImageField):
            continue
        try:
            ff = getattr(instance, field.name, None)
            if ff and ff.name:
                storage = field.storage
                if storage.exists(ff.name):
                    storage.delete(ff.name)
        except Exception:
            pass


try:
    _attach_image_validators_once()
except Exception:
    pass
