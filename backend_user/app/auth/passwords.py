from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash("dummy-password-used-only-for-timing")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password, password_hash)
        except UnknownHashError:
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(password, self._dummy_hash)
