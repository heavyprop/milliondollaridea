import getpass
import json
import os
import tempfile
from pathlib import Path

from .client import normalize_server, read_json, request
from .errors import SafeError


def load_config(path):
    try:
        data = json.loads(path.read_text())
        data["server"] = normalize_server(data["server"], data.get("allow_http", False))
        if not isinstance(data["token"], str) or not data["token"]:
            raise ValueError()
        return data
    except FileNotFoundError:
        raise SafeError("Run safe login first.") from None
    except (ValueError, KeyError, TypeError):
        raise SafeError("Invalid Safe configuration. Run safe login again.") from None


def login(args, config_path):
    server = normalize_server(args.server, args.allow_http)
    token = getpass.getpass(
        "CLI token (from Secure Hosting → Set up Safe CLI): "
    ).strip()
    if not token:
        raise SafeError("A token is required.")
    config = {"server": server, "token": token, "allow_http": args.allow_http}
    identity = read_json(request(config, "/hosting/api/me/"))
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=config_path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(config, stream)
        os.replace(temporary, config_path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print(f"Connected to {server} as {identity['username']}.")
