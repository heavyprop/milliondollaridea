import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request

from .errors import SafeError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward bearer tokens to a redirect target.
        return None


def normalize_server(value, allow_http=False):
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise SafeError(
            "Use a server origin such as https://example.com (no path or credentials)."
        )
    local = parsed.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme == "http" and not local and not allow_http:
        raise SafeError("Use HTTPS, or --allow-http for a trusted development network.")
    return value.rstrip("/")


def request(config, path, *, data=None, content_type=None):
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "User-Agent": "UnTrainable-Safe/0.1",
    }
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(config["server"] + path, data=data, headers=headers)
    try:
        return urllib.request.build_opener(NoRedirect()).open(req, timeout=120)
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read(8192)).get("error", f"HTTP {exc.code}")
        except (ValueError, AttributeError):
            message = (
                f"Server returned HTTP {exc.code}. Check the server address and token."
            )
        raise SafeError(message) from None
    except urllib.error.URLError as exc:
        raise SafeError(f"Cannot reach the server: {exc.reason}") from None


def read_json(response):
    with response:
        try:
            return json.loads(response.read(65536))
        except ValueError:
            raise SafeError("Server returned an invalid response.") from None
