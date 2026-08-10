"""고정 관리자 비밀번호를 터미널에서 입력받아 해시만 출력한다."""

from getpass import getpass

from app.core.password import hash_password

import re


MIN_PASSWORD_LENGTH = 12

def main() -> None:
    password = getpass("고정 관리자 비밀번호: ")
    confirmation = getpass("비밀번호 확인: ")

    PASSWORD_LENGTH = 8

    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )
    if password != confirmation:
        raise SystemExit("비밀번호가 일치하지 않습니다.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )

    print("\n아래 값을 backend_admin/.env에 한 번만 복사하세요.")
    print(f"ADMIN_PASSWORD_HASH={hash_password(password)}")
    print("평문 비밀번호는 파일이나 Git에 기록하지 마세요.")


if __name__ == "__main__":
    main()


def validate_password(password: str) -> None:
    if len(password) != 8:
        raise ValueError(
            "비밀번호는 정확히 8자여야 합니다."
        )

    if not re.search(r"[a-z]", password):
        raise ValueError(
            "영문 소문자가 필요합니다."
        )

    if not re.search(r"[A-Z]", password):
        raise ValueError(
            "영문 대문자가 필요합니다."
        )

    if not re.search(r"[0-9]", password):
        raise ValueError(
            "숫자가 필요합니다."
        )

    if not re.search(r"[^a-zA-Z0-9]", password):
        raise ValueError(
            "특수문자가 필요합니다."
        )
