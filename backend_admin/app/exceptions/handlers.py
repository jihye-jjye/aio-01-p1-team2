from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse



async def http_exception_handler(
    request: Request,
    exception: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exception.status_code,
        content={"success": False, "message": str(exception.detail)},
    )
    

async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "입력 내용을 확인해 주세요."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
