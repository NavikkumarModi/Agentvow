"""Verification of GitHub Actions OIDC tokens (RS256 against GitHub's published keys). Only RS256 is accepted: an `alg` of none or HS256 (key confusion) is refused. The key set is fetched through an
injected function (default: GitHub's JWKS URL) and cached; an unknown `kid` triggers at most one refresh per minute."""
import base64
import json
import time
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = ISSUER + "/.well-known/jwks"


class OidcError(Exception):
    pass


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def fetch_jwks() -> dict:
    with urllib.request.urlopen(urllib.request.Request(JWKS_URL, headers={"User-Agent": "agentvow-control-plane"}), timeout=10) as r:   # noqa: S310 (fixed https URL)
        return json.loads(r.read(200_000))


class OidcVerifier:
    def __init__(self, audience: str, jwks_fetch=fetch_jwks, issuer: str = ISSUER, now=time.time, skew: int = 60):
        self.audience, self.fetch, self.issuer, self.now, self.skew = audience, jwks_fetch, issuer, now, skew
        self._keys: dict = {}
        self._fetched = 0.0

    def _refresh(self) -> None:
        keys = {}
        for k in (self.fetch() or {}).get("keys", []):
            if k.get("kty") == "RSA" and k.get("kid") and k.get("n") and k.get("e"):
                keys[k["kid"]] = rsa.RSAPublicNumbers(int.from_bytes(_unb64(k["e"]), "big"), int.from_bytes(_unb64(k["n"]), "big")).public_key()
        self._keys, self._fetched = keys, self.now()

    def _key(self, kid: str):
        if kid not in self._keys and self.now() - self._fetched > 60:
            self._refresh()
        return self._keys.get(kid)

    def verify(self, token: str) -> dict:
        """-> claims, or raises OidcError. Checks: structure, alg RS256 only, known kid, signature, issuer, audience, expiry, not-before."""
        try:
            h, p, s = token.split(".")
            header, claims, sig = json.loads(_unb64(h)), json.loads(_unb64(p)), _unb64(s)
        except (ValueError, TypeError):
            raise OidcError("malformed token")
        if not isinstance(header, dict) or header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise OidcError("only RS256 tokens with a key id are accepted")
        key = self._key(header["kid"])
        if key is None:
            raise OidcError("unknown signing key")
        try:
            key.verify(sig, f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature:
            raise OidcError("bad signature")
        if not isinstance(claims, dict) or claims.get("iss") != self.issuer:
            raise OidcError("wrong issuer")
        aud = claims.get("aud")
        if not (aud == self.audience or (isinstance(aud, list) and self.audience in aud)):
            raise OidcError("wrong audience")
        now = self.now()
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= now - self.skew:
            raise OidcError("expired")
        if isinstance(claims.get("nbf"), (int, float)) and claims["nbf"] > now + self.skew:
            raise OidcError("not yet valid")
        return claims
