import ipaddress
import shlex
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.hosting.forms import TokenForm
from apps.hosting.models import AccessToken
from apps.hosting.services.tokens import issue_token


@login_required(login_url="/accounts/")
@never_cache
@require_http_methods(["GET", "POST"])
def cli_access(request):
    form = TokenForm(request.POST if request.method == "POST" else None)
    secret = None
    created_token = None
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if (
                AccessToken.objects.filter(
                    user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()
                ).count()
                >= 10
            ):
                form.add_error(
                    None,
                    "Revoke an existing token before creating another (limit: 10).",
                )
            else:
                created_token, secret = issue_token(
                    user,
                    form.cleaned_data["name"],
                    can_write=form.cleaned_data["can_write"],
                )
                form = TokenForm()
    tokens = AccessToken.objects.filter(
        user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).order_by("-created_at")
    server_url = request.build_absolute_uri("/").rstrip("/")
    parsed = urlsplit(server_url)
    local = parsed.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    login_command = f"safe login --server {shlex.quote(server_url)}"
    if parsed.scheme == "http" and not local:
        login_command += " --allow-http"
    return render(
        request,
        "hosting/cli_access.html",
        {
            "form": form,
            "token_secret": secret,
            "created_token": created_token,
            "tokens": tokens,
            "login_command": login_command,
            "get_command": f"safe get {shlex.quote(request.user.username + '/my-project')} ./downloaded-project",
        },
    )


@login_required(login_url="/accounts/")
@require_POST
def revoke_token(request, token_id):
    token = get_object_or_404(AccessToken, pk=token_id, user=request.user)
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])
    return redirect("hosting:cli_access")
