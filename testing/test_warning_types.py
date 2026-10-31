# mypy: allow-untyped-defs
from __future__ import annotations

import inspect

from _pytest import warning_types
from _pytest.pytester import Pytester
import pytest


@pytest.mark.parametrize(
    "warning_class",
    [
        w
        for n, w in vars(warning_types).items()
        if inspect.isclass(w) and issubclass(w, Warning)
    ],
)
def test_warning_types(warning_class: UserWarning) -> None:
    """Make sure all warnings declared in _pytest.warning_types are displayed as coming
    from 'pytest' instead of the internal module (#5452).
    """
    assert warning_class.__module__ == "pytest"


@pytest.mark.filterwarnings("error::pytest.PytestWarning")
def test_pytest_warnings_repr_integration_test(pytester: Pytester) -> None:
    """Small integration test to ensure our small hack of setting the __module__ attribute
    of our warnings actually works (#5452).
    """
    pytester.makepyfile(
        """
        import pytest
        import warnings

        def test():
            warnings.warn(pytest.PytestWarning("some warning"))
    """
    )
    result = pytester.runpytest()
    result.stdout.fnmatch_lines(["E       pytest.PytestWarning: some warning"])


@pytest.mark.filterwarnings("error")
def test_warn_explicit_for_annotates_errors_with_location():
    with pytest.raises(Warning, match=r"(?m)test\n at .*raises.py:\d+"):
        warning_types.warn_explicit_for(
            pytest.raises,  # type: ignore[arg-type]
            warning_types.PytestWarning("test"),
        )


def test_deprecated_constants_are_not_shared_instances() -> None:
    """Warning constants in _pytest.deprecated must not be shared Warning
    instances: under ``-W error`` the same object would be raised repeatedly,
    accumulating tracebacks across raises."""
    from _pytest import deprecated

    for name, value in vars(deprecated).items():
        assert not isinstance(value, Warning), name
        if isinstance(value, warning_types.UnformattedWarning):
            if "{" not in value.template:
                assert value.format() is not value.format(), name
