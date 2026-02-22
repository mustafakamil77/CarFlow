from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MaintenanceRequest
from .services import enqueue_new_request_email


@receiver(post_save, sender=MaintenanceRequest)
def maintenance_request_created(sender, instance, created, **kwargs):
    if created and instance.status == "new":
        enqueue_new_request_email(instance)
