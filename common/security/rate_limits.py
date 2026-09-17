from functools import wraps

from django.shortcuts import render
from django_ratelimit.core import is_ratelimited

from .suspicion import add_suspicion


def limit_requests(*, rate, group, method="POST", query_param=None):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            should_check = request.user.is_authenticated and request.method == method

            if query_param is not None:
                should_check = should_check and bool(
                    request.GET.get(query_param, "").strip()
                )

            if should_check and is_ratelimited(
                request,
                group=group,
                key="user",
                rate=rate,
                method=method,
                increment=True,
            ):
                is_htmx = request.headers.get("HX-Request") == "true"

                # increment the suspicion cache
                suspicion_response = add_suspicion(request)
                if suspicion_response is not None:
                    if is_htmx:
                        suspicion_response["HX-Redirect"] = suspicion_response[
                            "Location"
                        ]
                        del suspicion_response["Location"]
                        suspicion_response.status_code = 200
                    return suspicion_response

                template = (
                    "partials/rate_limit_message.html"
                    if is_htmx
                    else "errors/rate_limited.html"
                )
                response = render(request, template, status=429)
                response["Retry-After"] = "60"

                if is_htmx:
                    response["HX-Retarget"] = "#rate-limit-notice"
                    response["HX-Reswap"] = "innerHTML"
                return response

            return view(request, *args, **kwargs)

        return wrapped

    return decorator
