"""Shared public errors for authoring actions."""
class AuthoringError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self):
        return {'committed': False, 'code': self.code, 'message': str(self), **self.details}


def fail(code, message, **details):
    raise AuthoringError(code, message, **details)


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        fail('INVALID_ARGUMENT', f'{name} must be a nonempty string', parameter=name)
