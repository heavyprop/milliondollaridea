from django.contrib.auth import logout
from django.core.cache import cache
from django.shortcuts import redirect

# this is a file for logging suspicion,
# any actions which may seem as suspicios and be cached
# a constant can be tuned for how agressive, how much suspicion till they are logged out
HOW_MANY = 1
# right now it is if exceeding rate limits more than once, then logged out


def add_suspicion(request):
    if not request.user.is_authenticated:
        return None

    key = f"suspicion:{request.session.session_key}"

    if cache.add(key, 1, timeout=600):
        suspicion = 1
    else:
        try:
            suspicion = cache.incr(key)
        except ValueError:
            cache.add(key, 1, timeout=600)
            suspicion = 1

    if suspicion > HOW_MANY:
        cache.delete(key)
        logout(request)
        return redirect("boarding")

    return None
