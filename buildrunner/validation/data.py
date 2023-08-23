"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
from typing import List, Union
# pylint: disable=no-name-in-module
from pydantic import BaseModel


class ValidationItem(BaseModel):
    """
    Contains a single validation error or warning.
    """
    message: str
    field: Union[str, None] = None


class ValidationResult(BaseModel):
    """
    Contains the result of a validation method.
    """
    warnings: List[ValidationItem] = []
    errors: List[ValidationItem] = []

    @staticmethod
    def _convert(item: Union[str, ValidationItem]) -> ValidationItem:
        if isinstance(item, str):
            return ValidationItem(message=item)
        return item

    @classmethod
    def error(cls, message: Union[str, ValidationItem]) -> 'ValidationResult':
        """
        Utility method to create a validation result consisting of a single error.
        :param message: the error message
        :return: a validation result
        """
        return cls(errors=[cls._convert(message)])

    @classmethod
    def warning(cls, message: Union[str, ValidationItem]) -> 'ValidationResult':
        """
        Utility method to create a validation result consisting of a single warning.
        :param message: the warning message
        :return: a validation result
        """
        return cls(warnings=[cls._convert(message)])

    def add_error(self, message: Union[str, ValidationItem]) -> None:
        """
        Add an error to the result.
        :param message: the error message
        :return: None
        """
        self.errors.append(self._convert(message))

    def add_warning(self, message: Union[str, ValidationItem]) -> None:
        """
        Add a warning to the result.
        :param message: the warning message
        :return: None
        """
        self.warnings.append(self._convert(message))

    def merge_result(self, result: 'ValidationResult') -> None:
        """
        Merge the results of another validation result into this one.
        :param result: the result to merge
        :return: None
        """
        if result.errors:
            self.errors.extend(result.errors)
        if result.warnings:
            self.warnings.extend(result.warnings)

    def __str__(self) -> str:
        message = ''
        if self.errors:
            errors = ''.join([f'  {error.field}:  {error.message}\n' for error in self.errors])
            message += f'Errors:\n{errors}'

        if self.warnings:
            if message == '':
                message += '\n'

            warnings = ''.join([f'  {warning.field}:  {warning.message}\n' for warning in self.warnings])
            message += f'Warnings:\n{warnings}'

        return message

    def __repr__(self) -> str:
        return self.__str__()
