# mypy: allow-untyped-defs
from __future__ import annotations

import inspect
import string
import traceback

from _pytest import deprecated
from _pytest import warning_types
from _pytest.deprecated import check_ispytest
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


@pytest.mark.parametrize(
    "name", [n for n in vars(deprecated) if n.isupper() and not n.startswith("_")]
)
def test_deprecated_does_not_hold_warning_instances(name: str) -> None:
    """A warning instance shared by all warn() calls accumulates traceback
    frames each time it is raised, so _pytest.deprecated must not hold any."""
    assert not isinstance(getattr(deprecated, name), Warning)


@pytest.mark.parametrize(
    "unformatted",
    [
        w
        for w in vars(deprecated).values()
        if isinstance(w, warning_types.UnformattedWarning)
        and not any(field for _, field, _, _ in string.Formatter().parse(w.template))
    ],
    ids=lambda w: w.template[:30],
)
def test_deprecated_format_returns_fresh_instance(
    unformatted: warning_types.UnformattedWarning[Warning],
) -> None:
    first = unformatted.format()
    assert isinstance(first, unformatted.category)
    assert str(first) == unformatted.template
    assert unformatted.format() is not first


@pytest.mark.filterwarnings("error::pytest.PytestDeprecationWarning")
def test_deprecation_errors_do_not_accumulate_traceback() -> None:
    def raise_it() -> BaseException:
        with pytest.raises(pytest.PytestDeprecationWarning) as excinfo:
            check_ispytest(False)
        return excinfo.value

    first, second = raise_it(), raise_it()

    assert first is not second
    assert len(traceback.extract_tb(second.__traceback__)) == len(
        traceback.extract_tb(first.__traceback__)
    )


def test_deprecation_error_traceback_points_at_own_test(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        def test_first():
            pytest.yield_fixture()

        def test_second():
            pytest.yield_fixture()
        """
    )
    result = pytester.runpytest(
        "--tb=short", "-W", "error::pytest.PytestRemovedIn10Warning"
    )
    result.assert_outcomes(failed=2)
    result.stdout.fnmatch_lines(
        [
            "*_ test_first _*",
            "*:4: in test_first",
            "*_ test_second _*",
            "*:7: in test_second",
        ]
    )
    second_report = result.stdout.str().partition("_ test_second _")[2]
    assert "in test_first" not in second_report
