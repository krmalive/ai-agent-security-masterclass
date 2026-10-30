class ShopFastError(Exception):
    status_code = 400


class NotFound(ShopFastError):
    status_code = 404


class Forbidden(ShopFastError):
    status_code = 403


class Conflict(ShopFastError):
    status_code = 409


class InvalidOperation(ShopFastError):
    status_code = 422
