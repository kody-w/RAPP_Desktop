"""
RAPP Authentication System
Device Flow OAuth2 authentication for RAPP SaaS platform.

Similar to GitHub CLI device flow:
1. User runs `rapp login` or clicks "Login" in desktop app
2. Device code is generated and displayed
3. User visits https://rapp.ai/device and enters code
4. App polls for token completion
5. Token is stored locally for API access
"""

import os
import json
import time
import uuid
import hashlib
import secrets
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class RappPlan(Enum):
    """RAPP subscription plans - like Anthropic's Claude tiers"""
    FREE = "free"
    PRO = "pro"
    TEAMS = "teams"
    ENTERPRISE = "enterprise"


@dataclass
class RappUser:
    """RAPP user account"""
    user_id: str
    email: str
    name: str
    plan: RappPlan
    organization: Optional[str] = None
    api_key: Optional[str] = None
    created_at: Optional[str] = None

    # Usage limits by plan
    PLAN_LIMITS = {
        RappPlan.FREE: {
            "api_calls_per_day": 100,
            "agents_per_project": 3,
            "projects": 2,
            "storage_mb": 100,
            "support": "community"
        },
        RappPlan.PRO: {
            "api_calls_per_day": 5000,
            "agents_per_project": 25,
            "projects": 20,
            "storage_mb": 5000,
            "support": "email"
        },
        RappPlan.TEAMS: {
            "api_calls_per_day": 50000,
            "agents_per_project": 100,
            "projects": 100,
            "storage_mb": 50000,
            "team_members": 25,
            "support": "priority"
        },
        RappPlan.ENTERPRISE: {
            "api_calls_per_day": -1,  # Unlimited
            "agents_per_project": -1,
            "projects": -1,
            "storage_mb": -1,
            "team_members": -1,
            "support": "dedicated",
            "sla": True,
            "custom_deployment": True
        }
    }

    def get_limits(self) -> Dict[str, Any]:
        return self.PLAN_LIMITS.get(self.plan, self.PLAN_LIMITS[RappPlan.FREE])


@dataclass
class DeviceCodeResponse:
    """Response from device code request"""
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


@dataclass
class TokenResponse:
    """Response from token exchange"""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    scope: str


class RappAuthConfig:
    """RAPP Auth configuration"""
    # Production endpoints
    AUTH_BASE_URL = "https://auth.rapp.ai"
    API_BASE_URL = "https://api.rapp.ai"
    DEVICE_AUTH_URL = f"{AUTH_BASE_URL}/device/code"
    TOKEN_URL = f"{AUTH_BASE_URL}/oauth/token"
    USERINFO_URL = f"{API_BASE_URL}/v1/user"

    # Local development endpoints
    DEV_AUTH_BASE_URL = "http://localhost:7072"
    DEV_API_BASE_URL = "http://localhost:7071"

    # OAuth client credentials (public client)
    CLIENT_ID = "rapp-desktop-client"
    SCOPE = "openid profile email rapp:read rapp:write"

    # Token storage
    TOKEN_DIR = Path.home() / ".rapp" / "auth"
    TOKEN_FILE = TOKEN_DIR / "credentials.json"

    @classmethod
    def is_development(cls) -> bool:
        return os.environ.get("RAPP_ENV", "production") == "development"

    @classmethod
    def get_auth_url(cls) -> str:
        return cls.DEV_AUTH_BASE_URL if cls.is_development() else cls.AUTH_BASE_URL

    @classmethod
    def get_api_url(cls) -> str:
        return cls.DEV_API_BASE_URL if cls.is_development() else cls.API_BASE_URL


class RappAuth:
    """
    RAPP Authentication Manager

    Handles device flow authentication for RAPP Desktop and CLI.
    Stores tokens securely and manages refresh.

    Usage:
        auth = RappAuth()

        # Check if already logged in
        if auth.is_authenticated():
            user = auth.get_current_user()
            print(f"Logged in as {user.email}")
        else:
            # Start device flow login
            device_code = await auth.start_device_flow()
            print(f"Enter code {device_code.user_code} at {device_code.verification_uri}")

            # Wait for user to authorize
            token = await auth.poll_for_token(device_code)
            print("Login successful!")
    """

    def __init__(self):
        self.config = RappAuthConfig
        self._ensure_auth_dir()
        self._current_user: Optional[RappUser] = None
        self._token: Optional[TokenResponse] = None

    def _ensure_auth_dir(self):
        """Create auth directory if it doesn't exist"""
        self.config.TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    def _save_credentials(self, token: TokenResponse, user: RappUser):
        """Save credentials to local file"""
        data = {
            "token": {
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "token_type": token.token_type,
                "expires_in": token.expires_in,
                "scope": token.scope,
                "saved_at": datetime.utcnow().isoformat()
            },
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "plan": user.plan.value,
                "organization": user.organization,
                "api_key": user.api_key
            }
        }

        # Secure file permissions
        self.config.TOKEN_FILE.write_text(json.dumps(data, indent=2))
        os.chmod(self.config.TOKEN_FILE, 0o600)

    def _load_credentials(self) -> Optional[Tuple[TokenResponse, RappUser]]:
        """Load credentials from local file"""
        if not self.config.TOKEN_FILE.exists():
            return None

        try:
            data = json.loads(self.config.TOKEN_FILE.read_text())

            token = TokenResponse(
                access_token=data["token"]["access_token"],
                refresh_token=data["token"]["refresh_token"],
                token_type=data["token"]["token_type"],
                expires_in=data["token"]["expires_in"],
                scope=data["token"]["scope"]
            )

            user = RappUser(
                user_id=data["user"]["user_id"],
                email=data["user"]["email"],
                name=data["user"]["name"],
                plan=RappPlan(data["user"]["plan"]),
                organization=data["user"].get("organization"),
                api_key=data["user"].get("api_key")
            )

            return token, user
        except Exception:
            return None

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        if self._token and self._current_user:
            return True

        creds = self._load_credentials()
        if creds:
            self._token, self._current_user = creds
            return True

        return False

    def get_current_user(self) -> Optional[RappUser]:
        """Get the currently authenticated user"""
        if self.is_authenticated():
            return self._current_user
        return None

    def get_access_token(self) -> Optional[str]:
        """Get the current access token"""
        if self.is_authenticated():
            return self._token.access_token
        return None

    def get_api_key(self) -> Optional[str]:
        """Get the user's API key for direct API access"""
        user = self.get_current_user()
        return user.api_key if user else None

    async def start_device_flow(self) -> DeviceCodeResponse:
        """
        Start the device flow authentication.
        Returns a device code that the user should enter at the verification URL.
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "client_id": self.config.CLIENT_ID,
                "scope": self.config.SCOPE
            }

            async with session.post(
                f"{self.config.get_auth_url()}/device/code",
                data=payload
            ) as response:
                if response.status != 200:
                    raise AuthError(f"Failed to start device flow: {await response.text()}")

                data = await response.json()

                return DeviceCodeResponse(
                    device_code=data["device_code"],
                    user_code=data["user_code"],
                    verification_uri=data["verification_uri"],
                    verification_uri_complete=data.get(
                        "verification_uri_complete",
                        f"{data['verification_uri']}?user_code={data['user_code']}"
                    ),
                    expires_in=data["expires_in"],
                    interval=data.get("interval", 5)
                )

    async def poll_for_token(
        self,
        device_code: DeviceCodeResponse,
        on_pending: Optional[callable] = None
    ) -> TokenResponse:
        """
        Poll the auth server until the user completes authorization.

        Args:
            device_code: The device code response from start_device_flow
            on_pending: Optional callback called while waiting (for UI updates)

        Returns:
            TokenResponse on successful authorization

        Raises:
            AuthError on failure or timeout
        """
        start_time = time.time()
        interval = device_code.interval

        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < device_code.expires_in:
                payload = {
                    "client_id": self.config.CLIENT_ID,
                    "device_code": device_code.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                }

                async with session.post(
                    f"{self.config.get_auth_url()}/oauth/token",
                    data=payload
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        # Success! Got the token
                        token = TokenResponse(
                            access_token=data["access_token"],
                            refresh_token=data["refresh_token"],
                            token_type=data["token_type"],
                            expires_in=data["expires_in"],
                            scope=data.get("scope", self.config.SCOPE)
                        )

                        # Get user info
                        user = await self._fetch_user_info(token.access_token)

                        # Save credentials
                        self._save_credentials(token, user)
                        self._token = token
                        self._current_user = user

                        return token

                    error = data.get("error")

                    if error == "authorization_pending":
                        # User hasn't authorized yet, keep polling
                        if on_pending:
                            on_pending()
                        await asyncio.sleep(interval)
                        continue

                    elif error == "slow_down":
                        # Rate limited, increase interval
                        interval += 5
                        await asyncio.sleep(interval)
                        continue

                    elif error == "expired_token":
                        raise AuthError("Device code expired. Please try again.")

                    elif error == "access_denied":
                        raise AuthError("Authorization denied by user.")

                    else:
                        raise AuthError(f"Authentication failed: {error}")

        raise AuthError("Authentication timed out. Please try again.")

    async def _fetch_user_info(self, access_token: str) -> RappUser:
        """Fetch user info from the API"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {access_token}"}

            async with session.get(
                f"{self.config.get_api_url()}/v1/user",
                headers=headers
            ) as response:
                if response.status != 200:
                    raise AuthError(f"Failed to fetch user info: {await response.text()}")

                data = await response.json()

                return RappUser(
                    user_id=data["user_id"],
                    email=data["email"],
                    name=data.get("name", data["email"].split("@")[0]),
                    plan=RappPlan(data.get("plan", "free")),
                    organization=data.get("organization"),
                    api_key=data.get("api_key"),
                    created_at=data.get("created_at")
                )

    async def refresh_token(self) -> TokenResponse:
        """Refresh the access token using the refresh token"""
        if not self._token:
            raise AuthError("No token to refresh. Please login first.")

        async with aiohttp.ClientSession() as session:
            payload = {
                "client_id": self.config.CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": self._token.refresh_token
            }

            async with session.post(
                f"{self.config.get_auth_url()}/oauth/token",
                data=payload
            ) as response:
                if response.status != 200:
                    # Refresh failed, need to re-authenticate
                    self.logout()
                    raise AuthError("Session expired. Please login again.")

                data = await response.json()

                self._token = TokenResponse(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", self._token.refresh_token),
                    token_type=data["token_type"],
                    expires_in=data["expires_in"],
                    scope=data.get("scope", self.config.SCOPE)
                )

                # Update stored credentials
                self._save_credentials(self._token, self._current_user)

                return self._token

    def logout(self):
        """Logout and clear stored credentials"""
        if self.config.TOKEN_FILE.exists():
            self.config.TOKEN_FILE.unlink()

        self._token = None
        self._current_user = None

    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers for authenticated API requests"""
        token = self.get_access_token()
        if not token:
            raise AuthError("Not authenticated. Please login first.")

        return {
            "Authorization": f"Bearer {token}",
            "X-RAPP-Client": "desktop",
            "X-RAPP-Version": "1.0.0"
        }


class AuthError(Exception):
    """RAPP Authentication Error"""
    pass


# CLI interface
async def login_cli():
    """CLI login flow - similar to `gh auth login`"""
    auth = RappAuth()

    if auth.is_authenticated():
        user = auth.get_current_user()
        print(f"Already logged in as {user.email} ({user.plan.value} plan)")
        response = input("Login with a different account? (y/N): ")
        if response.lower() != 'y':
            return
        auth.logout()

    print("\n🔐 RAPP Authentication")
    print("=" * 40)

    # Start device flow
    print("\n⏳ Waiting for authorization...")
    device_code = await auth.start_device_flow()

    print(f"\n📋 Enter one-time code: {device_code.user_code}")
    print(f"🌐 at {device_code.verification_uri}")
    print("\nPress any key to copy to clipboard and open browser...")

    # Copy to clipboard (platform-specific)
    try:
        import subprocess
        if os.name == 'darwin':  # macOS
            subprocess.run(['pbcopy'], input=device_code.user_code.encode(), check=True)
        elif os.name == 'nt':  # Windows
            subprocess.run(['clip'], input=device_code.user_code.encode(), check=True)
        else:  # Linux
            subprocess.run(['xclip', '-selection', 'clipboard'], input=device_code.user_code.encode(), check=True)
    except:
        pass

    input()

    # Open browser
    try:
        import webbrowser
        webbrowser.open(device_code.verification_uri_complete)
    except:
        pass

    # Poll for token
    def on_pending():
        print(".", end="", flush=True)

    try:
        await auth.poll_for_token(device_code, on_pending)
        print("\n")

        user = auth.get_current_user()
        print(f"✅ Successfully logged in as {user.name} ({user.email})")
        print(f"📦 Plan: {user.plan.value.upper()}")
        if user.organization:
            print(f"🏢 Organization: {user.organization}")

        limits = user.get_limits()
        print(f"\n📊 Your limits:")
        print(f"   API calls/day: {limits['api_calls_per_day'] if limits['api_calls_per_day'] > 0 else 'Unlimited'}")
        print(f"   Projects: {limits['projects'] if limits['projects'] > 0 else 'Unlimited'}")
        print(f"   Storage: {limits['storage_mb']}MB" if limits['storage_mb'] > 0 else "   Storage: Unlimited")

    except AuthError as e:
        print(f"\n❌ Authentication failed: {e}")


async def logout_cli():
    """CLI logout"""
    auth = RappAuth()
    auth.logout()
    print("✅ Logged out successfully")


async def status_cli():
    """Show current auth status"""
    auth = RappAuth()

    if auth.is_authenticated():
        user = auth.get_current_user()
        print(f"✅ Logged in as {user.name} ({user.email})")
        print(f"📦 Plan: {user.plan.value.upper()}")
        if user.organization:
            print(f"🏢 Organization: {user.organization}")
        if user.api_key:
            print(f"🔑 API Key: {user.api_key[:8]}...{user.api_key[-4:]}")
    else:
        print("❌ Not logged in")
        print("Run `rapp login` to authenticate")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python rapp_auth.py [login|logout|status]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "login":
        asyncio.run(login_cli())
    elif command == "logout":
        asyncio.run(logout_cli())
    elif command == "status":
        asyncio.run(status_cli())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
