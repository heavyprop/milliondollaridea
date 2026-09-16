import argparse
import os
from pathlib import Path

from .archive import ArchiveError
from .commands import get, publish
from .config import load_config, login
from .errors import SafeError


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="safe",
        description="Publish and download project folders with Secure Hosting.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            os.environ.get("SAFE_CONFIG", Path.home() / ".config/untrainable/safe.json")
        ),
        help="Path to local credentials",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    login_parser = commands.add_parser("login", help="Save a CLI access token")
    login_parser.add_argument("--server", default="http://127.0.0.1:8000")
    login_parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Allow HTTP on a trusted development network",
    )
    publish_parser = commands.add_parser(
        "publish", help="Upload or replace a whole project folder"
    )
    publish_parser.add_argument("folder", nargs="?", default=".")
    publish_parser.add_argument(
        "--project", help="Project slug or owner/slug (defaults to folder name)"
    )
    get_parser = commands.add_parser("get", help="Download into a new folder")
    get_parser.add_argument("project", help="owner/project-name")
    get_parser.add_argument("destination", nargs="?")
    commands.add_parser("logout", help="Remove the saved token from this computer")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            login(args, args.config)
        elif args.command == "logout":
            args.config.unlink(missing_ok=True)
            print(
                "Local credentials removed. Revoke the token on the website if it is no longer needed."
            )
        elif args.command == "publish":
            publish(args, load_config(args.config))
        else:
            get(args, load_config(args.config))
    except (SafeError, ArchiveError, OSError, ValueError) as exc:
        parser.exit(1, f"safe: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nsafe: cancelled\n")
