from __future__ import annotations

from _pytest.config import ExitCode
from _pytest.pytester import Pytester
import pytest


@pytest.mark.parametrize("option", ["--strict-markers", "--strict"])
def test_strict_markers_unknown_marker_in_m_expression(
    pytester: Pytester, option: str
) -> None:
    pytester.makeini(
        """
        [pytest]
        markers =
            registered: a registered marker
        """
    )
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.registered
        def test_a(): pass
        """
    )
    result = pytester.runpytest(option, "-m", "registered and not (typo1 or typo2)")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(
        ["*Unknown marker(s) in '-m' expression: typo1, typo2*"]
    )
    result = pytester.runpytest(option, "-m", "registered")
    result.assert_outcomes(passed=1)
    result = pytester.runpytest("-m", "typo1")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


def test_expression_idents() -> None:
    from _pytest.mark.expression import Expression

    expr = Expression.compile("a and not (b or c(x=1, y='z'))")
    assert expr.idents() == frozenset({"a", "b", "c"})
