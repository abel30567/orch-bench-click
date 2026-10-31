from __future__ import annotations

from _pytest.config import ExitCode
from _pytest.config import RegisteredMarker
from _pytest.mark.expression import Expression
from _pytest.pytester import Pytester
import pytest


@pytest.mark.parametrize(
    ("expr", "idents"),
    [
        ("", set()),
        ("foo", {"foo"}),
        ("not foo and (bar or foo)", {"foo", "bar"}),
        ("foo(key=1, other='value') or bar(key=True)", {"foo", "bar"}),
    ],
)
def test_expression_idents(expr: str, idents: set[str]) -> None:
    assert Expression.compile(expr).idents() == idents


def test_iter_registered_markers(pytester: Pytester) -> None:
    pytester.makeini(
        """
        [pytest]
        markers =
            slow: a slow test: really
            needs(resource): a test with a signature
            bare
        """
    )
    config = pytester.parseconfigure()
    assert list(config._iter_registered_markers())[:3] == [
        RegisteredMarker("slow"),
        RegisteredMarker("needs"),
        RegisteredMarker("bare"),
    ]


@pytest.fixture
def marked_test(pytester: Pytester) -> None:
    pytester.makeini(
        """
        [pytest]
        markers = slow: a slow test
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.slow
        def test_slow(): pass
        """
    )


@pytest.mark.usefixtures("marked_test")
@pytest.mark.parametrize(
    ("expr", "names"),
    [
        ("typo", "typo"),
        ("not typo", "typo"),
        ("slow and (zzz or aaa)", "aaa, zzz"),
        ("typo(key=1)", "typo"),
    ],
)
@pytest.mark.parametrize("option", ["--strict-markers", "--strict"])
def test_unknown_marker_in_expression(
    pytester: Pytester, option: str, expr: str, names: str
) -> None:
    result = pytester.runpytest(option, "-m", expr)
    assert result.ret == ExitCode.USAGE_ERROR
    message = f"ERROR: Unknown marker(s) in '-m' expression: {names}"
    assert message in result.stderr.lines


@pytest.mark.usefixtures("marked_test")
@pytest.mark.parametrize(
    "expr", ["slow", "slow(key=1) or not slow", "skipif or parametrize"]
)
def test_registered_markers_in_expression(pytester: Pytester, expr: str) -> None:
    result = pytester.runpytest("--strict-markers", "-m", expr)
    assert result.ret in (ExitCode.OK, ExitCode.NO_TESTS_COLLECTED)


@pytest.mark.usefixtures("marked_test")
def test_marker_registered_by_conftest_in_expression(pytester: Pytester) -> None:
    pytester.makeconftest(
        """
        def pytest_configure(config):
            config.addinivalue_line("markers", "dynamic: added by a conftest")
        """
    )
    result = pytester.runpytest("--strict-markers", "-m", "dynamic")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


@pytest.mark.usefixtures("marked_test")
def test_unknown_marker_in_expression_not_strict(pytester: Pytester) -> None:
    result = pytester.runpytest("-m", "typo")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


@pytest.mark.usefixtures("marked_test")
def test_strict_markers_takes_precedence_over_strict(pytester: Pytester) -> None:
    pytester.makeini(
        """
        [pytest]
        strict = true
        strict_markers = false
        """
    )
    result = pytester.runpytest("-m", "typo")
    assert result.ret == ExitCode.NO_TESTS_COLLECTED


@pytest.mark.usefixtures("marked_test")
@pytest.mark.parametrize("numprocesses", ["1", "2"])
def test_unknown_marker_in_expression_xdist(
    pytester: Pytester, monkeypatch: pytest.MonkeyPatch, numprocesses: str
) -> None:
    pytest.importorskip("xdist")
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    result = pytester.runpytest_subprocess("-n", numprocesses, "--strict", "-m", "typo")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*Unknown marker(s) in '-m' expression: typo"])
    result.stdout.no_fnmatch_line("*INTERNALERROR*")
    result.stderr.no_fnmatch_line("*INTERNALERROR*")


def test_unknown_marker_in_expression_xdist_no_tests(
    pytester: Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("xdist")
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    result = pytester.runpytest_subprocess("-n2", "--strict", "-m", "typo")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*Unknown marker(s) in '-m' expression: typo"])


def test_marker_from_nested_conftest_in_expression_xdist(
    pytester: Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only workers load this conftest, as the controller does not collect."""
    pytest.importorskip("xdist")
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    sub = pytester.mkdir("sub")
    sub.joinpath("conftest.py").write_text(
        "def pytest_configure(config):\n"
        "    config.addinivalue_line('markers', 'subdyn: added by a conftest')\n",
        encoding="utf-8",
    )
    sub.joinpath("test_sub.py").write_text(
        "import pytest\n@pytest.mark.subdyn\ndef test_sub(): pass\n",
        encoding="utf-8",
    )
    result = pytester.runpytest_subprocess("-n2", "--strict", "-m", "subdyn")
    assert result.ret == ExitCode.OK
    result.assert_outcomes(passed=1)
