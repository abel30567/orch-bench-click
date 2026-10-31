# mypy: allow-untyped-defs
from __future__ import annotations

import inspect
import warnings

from _pytest import deprecated
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


@pytest.mark.parametrize("name", [name for name in vars(deprecated) if name.isupper()])
def test_deprecated_warnings_are_not_shared_instances(name: str) -> None:
    """A warning instance raised under ``-W error`` keeps its traceback, so
    deprecated.py must not hold instances that are raised more than once."""
    assert not isinstance(getattr(deprecated, name), Warning)


def test_deprecated_warning_traceback_does_not_accumulate() -> None:
    def trigger() -> pytest.ExceptionInfo[pytest.PytestDeprecationWarning]:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(pytest.PytestDeprecationWarning) as excinfo:
                deprecated.check_ispytest(False)
        return excinfo

    first = trigger()
    second = trigger()
    assert first.value is not second.value
    assert len(first.traceback) == len(second.traceback)
