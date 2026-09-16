from functools import wraps

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.hosting.services.quotas import QuotaExceeded
from apps.hosting.services.tokens import authenticate_token
from safe_cli.archive import ArchiveError


def endpoint(method):
    """Session cookies never authorize CLI endpoints; a bearer token is required."""

    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != method:
                response = JsonResponse({"error": f"Use {method}."}, status=405)
                response["Allow"] = method
            else:
                authorization = request.headers.get("Authorization", "")
                scheme, _, secret = authorization.partition(" ")
                try:
                    if scheme.lower() != "bearer" or not secret or len(secret) > 256:
                        raise PermissionDenied()
                    token = authenticate_token(secret)
                except PermissionDenied:
                    response = JsonResponse(
                        {"error": "Invalid or expired token. Run safe login."},
                        status=401,
                    )
                    response["WWW-Authenticate"] = "Bearer"
                else:
                    try:
                        response = view(request, token, *args, **kwargs)
                    except Http404:
                        response = JsonResponse(
                            {"error": "Project not found or access denied."}, status=404
                        )
                    except PermissionDenied as exc:
                        response = JsonResponse(
                            {"error": str(exc) or "Access denied."}, status=403
                        )
                    except (ArchiveError, ValidationError) as exc:
                        message = (
                            "; ".join(exc.messages)
                            if isinstance(exc, ValidationError)
                            else str(exc)
                        )
                        response = JsonResponse({"error": message}, status=400)
                    except QuotaExceeded as exc:
                        response = JsonResponse({"error": str(exc)}, status=429)
                        response["Retry-After"] = "3600"
            response["Cache-Control"] = "private, no-store"
            response["X-Content-Type-Options"] = "nosniff"
            return response

        return wrapped

    return decorate
