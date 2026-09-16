from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render


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


def profile(request):
    if not request.user.is_authenticated:
        return redirect("home")
    return render(
        request,
        "accounts/profile.html",
        {
            "username": request.user.username,
            "date": request.user.date_joined,
        },
    )
