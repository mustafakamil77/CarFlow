from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver


def ensure_role_groups():
    roles = ["Admin", "Manager", "Driver"]
    for name in roles:
        Group.objects.get_or_create(name=name)


@receiver(post_migrate)
def create_groups(sender, **kwargs):
    ensure_role_groups()