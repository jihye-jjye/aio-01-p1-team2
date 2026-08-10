class LoginIdAlreadyExistsError(ValueError):
    def __init__(self) -> None:
        super().__init__("이미 사용 중인 아이디입니다.")
