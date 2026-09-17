from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.feed.selectors import users_threads
from apps.notifcation.selectors import users_notifications

from .models import UserBlock


def auth_page(request):
    if request.user.is_authenticated:
        return redirect("home")

    signup_form = UserCreationForm(auto_id="signup_%s")
    signin_form = AuthenticationForm(auto_id="signin_%s")

    if request.method == "POST":
        if "signup" in request.POST:
            signup_form = UserCreationForm(request.POST, auto_id="signup_%s")
            if signup_form.is_valid():
                user = signup_form.save()
                login(request, user)
                return redirect("home")

        if "signin" in request.POST:
            signin_form = AuthenticationForm(
                request, data=request.POST, auto_id="signin_%s"
            )
            if signin_form.is_valid():
                user = signin_form.get_user()
                login(request, user)
                return redirect("home")

    return render(
        request,
        "accounts/auth.html",
        {
            "signup_form": signup_form,
            "signin_form": signin_form,
        },
    )


def view_user(request, username):
    if not request.user.is_authenticated:
        return redirect("home")

    user = get_object_or_404(get_user_model(), username=username)
    is_own_profile = user == request.user

    template = "accounts/profile.html" if is_own_profile else "accounts/accounts.html"

    return render(
        request,
        template,
        {
            "username": user.username,
            "date": user.date_joined,
            "threads": users_threads(user),
            "notifications": users_notifications(request.user)
            if is_own_profile
            else [],
            "is_blocked": UserBlock.objects.filter(
                blocker=request.user, blocked=user
            ).exists(),
            "is_own_profile": user == request.user,  # is primary key users primary key
            "blocked_users": (
                UserBlock.objects.filter(blocker=request.user)
                .select_related("blocked")
                .order_by("blocked__username")
                if is_own_profile
                else []
            ),
        },
    )


def profile(request):
    if not request.user.is_authenticated:
        return redirect("home")

    return redirect("view_user", username=request.user.username)


@require_POST
def block_user(request, username):
    if not request.user.is_authenticated:
        return redirect("home")

    user = get_object_or_404(get_user_model(), username=username)

    if user == request.user:
        return HttpResponseBadRequest("You cannot block yourself")

    UserBlock.objects.get_or_create(blocker=request.user, blocked=user)

    return redirect("home")


@require_POST
def unblock_user(request, username):
    if not request.user.is_authenticated:
        return redirect("home")

    user = get_object_or_404(get_user_model(), username=username)
    UserBlock.objects.filter(blocker=request.user, blocked=user).delete()
    if request.POST.get("return_to") == "profile":
        return redirect("profile")
    return redirect("view_user", username=user.username)
