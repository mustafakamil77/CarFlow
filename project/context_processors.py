from staff.models import Employee


def employee_profile(request):
    if not request.user.is_authenticated:
        return {"employee_profile": None}
    profile = Employee.objects.filter(user=request.user).first()
    return {"employee_profile": profile}
