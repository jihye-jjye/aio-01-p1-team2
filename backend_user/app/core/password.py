"""비밀번호를 안전하게 저장하고 로그인할 때 비교하는 함수입니다.

중요:
    사용자가 입력한 비밀번호를 DB에 그대로 저장하면 안 됩니다.
    이 파일은 비밀번호를 원래 값으로 되돌릴 수 없는 해시 문자열로 바꿉니다.
"""

import hashlib
import hmac
import secrets


# PBKDF2 계산을 반복하는 횟수입니다.
# 반복 횟수가 많을수록 비밀번호 해시 계산에 시간이 더 걸리므로,
# 공격자가 수많은 비밀번호를 빠르게 대입하기 어려워집니다.
ITERATIONS = 200_000

# pwd01 => fdsafdsafdsafdsafdsafdsafdsaffdas
def hash_password(password: str) -> str:
    """회원가입 비밀번호를 DB에 저장할 해시 문자열로 만듭니다."""

    # salt는 사용자마다 새로 만드는 임의의 문자열입니다.
    # 같은 비밀번호를 사용한 사람도 서로 다른 해시가 저장되게 합니다.
    salt = secrets.token_hex(16)

    # PBKDF2는 비밀번호, salt, 반복 횟수를 이용해 해시를 만듭니다.
    # sha256은 PBKDF2 내부에서 사용하는 해시 알고리즘입니다.
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    ).hex()

    # 로그인할 때 같은 방법으로 다시 계산할 수 있도록
    # 알고리즘 이름, 반복 횟수, salt, 결과를 $로 연결해 저장합니다.
    # 실제 저장 형태:
    # pbkdf2_sha256$200000$salt값$비밀번호해시값
    return f"pbkdf2_sha256${ITERATIONS}${salt}${password_hash}"


def verify_password(password: str, saved_password: str) -> bool:
    """로그인 비밀번호가 DB에 저장된 해시와 같은지 확인합니다."""

    try:
        # 회원가입 때 $로 연결했던 네 부분을 다시 분리합니다.
        algorithm, iterations, salt, expected_hash = saved_password.split("$")

        # 이 예제에서 만든 PBKDF2 해시가 아니면 비교하지 않습니다.
        if algorithm != "pbkdf2_sha256":
            return False

        # 로그인 화면에 입력된 비밀번호를 DB에 저장된 salt와 반복 횟수로
        # 다시 해시합니다. 원래 비밀번호를 복호화하는 과정이 아닙니다.
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()

        # 새로 만든 해시와 DB의 해시가 같으면 올바른 비밀번호입니다.
        # compare_digest는 일반 == 비교보다 안전하게 문자열을 비교합니다.
        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError):
        # DB 값의 형식이 잘못되었거나 값이 없는 경우 로그인에 실패합니다.
        return False
