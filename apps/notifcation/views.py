from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .selectors import users_notifications


@login_required
def get_users_notifications(request):
    return render(
        request,
        "notifcation/details.html",
        {"notifications": users_notifications(request.user)},
    )
