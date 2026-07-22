import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.core.db import DAOError, DAOIntegrityError
from src.core.db.dao import catch_sqlalchemy_exception


def test_integrity_errors_keep_a_specific_dao_type() -> None:
    with pytest.raises(DAOIntegrityError):
        with catch_sqlalchemy_exception():
            raise IntegrityError("INSERT", {}, ValueError("duplicate"))


def test_other_sqlalchemy_errors_keep_a_dao_type() -> None:
    with pytest.raises(DAOError):
        with catch_sqlalchemy_exception():
            raise SQLAlchemyError("database unavailable")
