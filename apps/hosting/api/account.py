from django.http import JsonResponse

from .decorators import endpoint


@endpoint("GET")
def me(request, token):
    return JsonResponse(
        {"username": token.user.get_username(), "can_publish": token.can_write}
    )
