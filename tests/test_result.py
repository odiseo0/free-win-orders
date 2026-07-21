from dataclasses import FrozenInstanceError

import pytest

from src.core import Err, Ok


def test_ok_contains_an_immutable_value() -> None:
    result = Ok(42)

    assert result.value == 42

    with pytest.raises(FrozenInstanceError):
        result.value = 0


def test_err_contains_an_immutable_error() -> None:
    error = ValueError("invalid value")
    result = Err(error)

    assert result.error is error

    with pytest.raises(FrozenInstanceError):
        result.error = ValueError("another error")
