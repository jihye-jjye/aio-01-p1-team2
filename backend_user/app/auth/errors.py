class LoginIdAlreadyExistsError(ValueError):
    def __init__(self) -> None:
        super().__init__("이미 사용 중인 아이디입니다.")


class AccountNotFoundError(LookupError):
    def __init__(self) -> None:
        super().__init__("계정을 찾을 수 없습니다.")
