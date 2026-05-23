class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message or self.code)
        self.message = message or self.code
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class PermissionError(AppError):
    status_code = 403
    code = "forbidden"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class ProcessingError(AppError):
    status_code = 500
    code = "processing_error"
