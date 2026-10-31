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


def test_deprecated_module_has_no_shared_warning_instances() -> None:
    """Warning constants in _pytest.deprecated must not be shared instances:
    under ``-W error``, ``warnings.warn()`` raises the given object itself, and
    a shared exception accumulates traceback frames across raises."""
    from _pytest import deprecated

    for name, value in vars(deprecated).items():
        assert not isinstance(value, Warning), name


@pytest.mark.filterwarnings("error")
def test_deprecation_warning_traceback_does_not_accumulate() -> None:
    from _pytest.deprecated import check_ispytest

    def tb_depth(exc: BaseException) -> int:
        depth = 0
        tb = exc.__traceback__
        while tb is not None:
            depth += 1
            tb = tb.tb_next
        return depth

    raised = []
    for _ in range(3):
        with pytest.raises(pytest.PytestDeprecationWarning) as excinfo:
            check_ispytest(False)
        raised.append(excinfo.value)
    assert len({id(e) for e in raised}) == len(raised)
    assert len({tb_depth(e) for e in raised}) == 1
