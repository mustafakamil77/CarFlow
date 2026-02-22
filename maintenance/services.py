from django.core.mail import send_mail
from django_q.tasks import async_task
from django.contrib.auth.models import Group


def _send_new_request_email(subject, message, recipient_list):
    send_mail(subject, message, None, recipient_list)


def enqueue_new_request_email(request):
    try:
        group = Group.objects.get(name="Maintenance Technician")
        emails = list(group.user_set.exclude(email="").values_list("email", flat=True))
    except Group.DoesNotExist:
        emails = []
    subject = f"New Maintenance Request: {request.title}"
    message = f"A new maintenance request was created for car {request.car.plate_number}.\n\n{request.description}"
    async_task(_send_new_request_email, subject, message, emails)
