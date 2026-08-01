"""
OAuth2 authentication for the Oura API.

OAuth2 is how apps get permission to read your Oura data without
sharing your Oura password. The flow works like this:

  1. Your script opens a browser URL → you log into Oura and click "Allow"
  2. Oura redirects back to localhost with a temporary "authorization code"
  3. Your script exchanges that code for an access_token + refresh_token
  4. The access_token is used for API calls; the refresh_token renews it later
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Oura OAuth2 endpoints (from official docs)
AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
API_BASE = "https://api.ouraring.com/v2"

TOKENS_PATH = Path(__file__).parent / "data" / "tokens.json"

# Scopes = what data we're asking permission to read
SCOPES = "email personal daily heartrate"


def load_tokens() -> dict | None:
    """Load saved tokens from disk, or return None if not logged in yet."""
    if not TOKENS_PATH.exists():
        return None
    return json.loads(TOKENS_PATH.read_text())


def save_tokens(tokens: dict) -> None:
    """Save tokens so we don't have to log in every time."""
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2))
    print(f"Tokens saved to {TOKENS_PATH}")


def _get_credentials() -> tuple[str, str, str]:
    """Load client_id, client_secret, and redirect_uri from .env."""
    client_id = os.getenv("OURA_CLIENT_ID", "").strip()
    client_secret = os.getenv("OURA_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("OURA_REDIRECT_URI", "http://localhost:8080/callback").strip()

    placeholders = {"your_client_id_here", "your_client_secret_here", ""}
    if client_id in placeholders or client_secret in placeholders:
        raise ValueError(
            "Your .env file still has placeholder values.\n"
            "Open .env, paste your real Client ID and Client Secret from\n"
            "https://developer.ouraring.com, then save the file (Cmd+S)."
        )

    if not client_id or not client_secret:
        raise ValueError(
            "Missing OURA_CLIENT_ID or OURA_CLIENT_SECRET in .env file.\n"
            "Copy .env.example to .env and fill in your credentials."
        )
    return client_id, client_secret, redirect_uri


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the URL that sends the user to Oura's login page."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict:
    """Exchange the one-time authorization code for access + refresh tokens."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """
    Get a new access token using the refresh token.

    Important: Oura refresh tokens are single-use. Each refresh returns a
    NEW refresh_token that you must save — the old one stops working.
    """
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _start_callback_server(port: int) -> Callable[[], str]:
    """
    Bind to localhost immediately, then wait for Oura's redirect.

    Returns a function that blocks until the authorization code arrives.
    The server must be listening BEFORE the browser opens, otherwise
    Oura's redirect can arrive with nobody home.
    """
    auth_code: str | None = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal auth_code
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)

            if "error" in params:
                self._respond(400, f"Authorization denied: {params['error'][0]}")
                return

            auth_code = params.get("code", [None])[0]
            if auth_code:
                self._respond(200, "Success! You can close this tab and return to the terminal.")
            else:
                self._respond(400, "No authorization code received.")

        def _respond(self, status: int, message: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode())

        def log_message(self, format: str, *args) -> None:
            pass

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    try:
        server = ReusableHTTPServer(("localhost", port), CallbackHandler)
    except OSError as err:
        if err.errno == 48:
            raise RuntimeError(
                f"Port {port} is already in use (probably a previous login attempt).\n"
                f"Free it with:\n\n"
                f"  lsof -ti :{port} | xargs kill -9\n\n"
                f"Then run: python main.py auth"
            ) from err
        raise

    def wait_for_code() -> str:
        print(f"Callback server listening on http://localhost:{port}/callback")
        server.handle_request()
        server.server_close()
        if not auth_code:
            raise RuntimeError("Login failed — no authorization code received.")
        return auth_code

    return wait_for_code


def _run_local_callback_server(port: int) -> str:
    """Start the callback server and block until Oura redirects back."""
    return _start_callback_server(port)()


def authenticate() -> dict:
    """Run the full OAuth2 login flow and return the token dict."""
    client_id, client_secret, redirect_uri = _get_credentials()
    state = secrets.token_urlsafe(16)
    auth_url = build_authorize_url(client_id, redirect_uri, state)

    port = int(urllib.parse.urlparse(redirect_uri).port or 8080)

    # Start listening BEFORE opening the browser
    wait_for_code = _start_callback_server(port)

    print("\n--- Step 1: Open this URL in your browser and log into Oura ---\n")
    print(auth_url)
    print()
    webbrowser.open(auth_url)

    print("\nWaiting for you to click Allow in the browser...\n")
    code = wait_for_code()

    print("\n--- Step 2: Exchanging authorization code for tokens ---\n")
    tokens = exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
    save_tokens(tokens)
    print("Authentication complete!")
    return tokens


def get_valid_access_token() -> str:
    """Return a working access token, refreshing automatically if expired."""
    client_id, client_secret, _ = _get_credentials()
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No saved tokens found. Run: python main.py auth")

    # Test the token with a lightweight API call
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = requests.get(f"{API_BASE}/usercollection/personal_info", headers=headers, timeout=30)

    if response.status_code == 401:
        print("Access token expired — refreshing...")
        tokens = refresh_access_token(tokens["refresh_token"], client_id, client_secret)
        save_tokens(tokens)

    elif not response.ok:
        response.raise_for_status()

    return tokens["access_token"]
