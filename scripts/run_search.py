"""Run Go search with the same .env database configuration as Django."""

import subprocess

from config.environment import BASE_DIR, load_environment, required


def main():
    load_environment()
    required("DATABASE_URL")
    return subprocess.call(
        ["go", "run", "./cmd/search"], cwd=BASE_DIR / "apps/search/go"
    )


if __name__ == "__main__":
    raise SystemExit(main())
