import time
from typing import Set

class TokenBlacklistEngine:
    """
    In-memory / Redis-compatible token revocation kill switch.
    Allows instant session invalidation for rogue or suspended accounts.
    """
    _revoked_tokens: Set[str] = set()

    @classmethod
    def revoke_token(cls, token: str):
        cls._revoked_tokens.add(token)

    @classmethod
    def is_blacklisted(cls, token: str) -> bool:
        return token in cls._revoked_tokens

token_blacklist = TokenBlacklistEngine
