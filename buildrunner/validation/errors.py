"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
from typing import Union

from pydantic import ValidationError


class Errors:
    """ Error class for storing validation errors """
    class Error:
        """ Error class for storing validation error """
        def __init__(self, field: str, message: str):
            self.field: str = field
            self.message: Union[str, None] = message

    def __init__(self):
        self.errors = []

    def add(self, field: str, message: str):
        """ Add an error """
        self.errors.append(self.Error(field, message))

    def count(self):
        """ Return the number of errors """
        return len(self.errors)

    def __str__(self):
        return '\n'.join([f'  {error.field}:  {error.message}' for error in self.errors])

    def __repr__(self):
        return self.__str__()


def get_validation_errors(exc: ValidationError) -> Errors:
    """ Get validation errors to an Errors object """
    errors = Errors()
    for error in exc.errors():
        loc = [str(item) for item in error["loc"]]
        if error["type"] == "value_error.extra":
            errors.add(field='.'.join(loc), message='not a valid field, please check the spelling and documentation')
        else:
            errors.add(field='.'.join(loc), message=f'{error["msg"]} ({error["type"]})')
    return errors
