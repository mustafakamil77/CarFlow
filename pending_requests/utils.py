from django.core.mail import send_mail
from django.conf import settings

def send_request_status_notification(pending_request, action, reason=None):
    subject = f"Your QR Request for {pending_request.car.plate_number} has been {action}"
    
    message = f"Dear {pending_request.submitter_name},\n\n"
    message += f"Your request for car {pending_request.car.plate_number} submitted on {pending_request.submitted_at.strftime('%Y-%m-%d %H:%M')}"

    if hasattr(pending_request, 'mileage'):
        message += f" (Mileage Report: {pending_request.mileage} km)"
    elif hasattr(pending_request, 'description'):
        message += f" (Maintenance Request: {pending_request.description[:50]}...)"
    
    message += f" has been {action} by an administrator.\n\n"

    if reason:
        message += f"Reason for {action}: {reason}\n\n"
    
    message += "Thank you for using our service.\n"
    message += f"{settings.SITE_NAME} Team" # Assuming SITE_NAME is defined in settings

    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [pending_request.submitter_contact] # Assuming submitter_contact is an email address

    if recipient_list and from_email:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
