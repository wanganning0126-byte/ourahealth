"""
Oura Health Analytics — main entry point.

Usage:
    python main.py auth       # Log in with Oura (run this first, once)
    python main.py download   # Download your data to CSV files
    python main.py all        # Auth + download in one go
"""

import sys

from auth import authenticate
from download import download_all


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "auth":
        authenticate()
    elif command == "download":
        download_all()
    elif command == "all":
        authenticate()
        download_all()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
