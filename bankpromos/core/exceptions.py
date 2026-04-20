from typing import Optional


class PromosException(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NavigationError(PromosException):
    pass


class ScrapingError(PromosException):
    pass


class ParseError(PromosException):
    pass


class AntiBotDetectedError(PromosException):
    pass