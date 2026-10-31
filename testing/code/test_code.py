# mypy: allow-untyped-defs
from __future__ import annotations

import ast
import re
import sys
from types import FrameType
from unittest import mock

from _pytest._code import Code
from _pytest._code import ExceptionInfo
from _pytest._code import Frame
from _pytest._code import Source
from _pytest._code.code import ExceptionChainRepr
from _pytest._code.code import ExceptionInfoFormatter
from _pytest._code.code import ReprFuncArgs
from _pytest._code.source import _statement_linenos
from _pytest._code.source import get_statement_startend2
import pytest


def test_ne() -> None:
    code1 = Code(compile('foo = "bar"', "", "exec"))
    assert code1 == code1
    code2 = Code(compile('foo = "baz"', "", "exec"))
    assert code2 != code1


def test_code_gives_back_name_for_not_existing_file() -> None:
    name = "abc-123"
    co_code = compile("pass\n", name, "exec")
    assert co_code.co_filename == name
    code = Code(co_code)
    assert str(code.path) == name
    assert code.fullsource is None


def test_code_from_function_with_class() -> None:
    class A:
        pass

    with pytest.raises(TypeError):
        Code.from_function(A)


def x() -> None:
    raise NotImplementedError()


def test_code_fullsource() -> None:
    code = Code.from_function(x)
    full = code.fullsource
    assert "test_code_fullsource()" in str(full)


def test_code_source() -> None:
    code = Code.from_function(x)
    src = code.source()
    expected = """def x() -> None:
    raise NotImplementedError()"""
    assert str(src) == expected


def test_frame_getsourcelineno_myself() -> None:
    def func() -> FrameType:
        return sys._getframe(0)

    f = Frame(func())
    source, lineno = f.code.fullsource, f.lineno
    assert source is not None
    assert source[lineno].startswith("        return sys._getframe(0)")


def test_getstatement_empty_fullsource() -> None:
    def func() -> FrameType:
        return sys._getframe(0)

    f = Frame(func())
    with mock.patch.object(f.code.__class__, "fullsource", None):
        assert f.statement == Source("")


def test_code_from_func() -> None:
    co = Code.from_function(test_frame_getsourcelineno_myself)
    assert co.firstlineno
    assert co.path


def test_unicode_handling() -> None:
    value = "ąć".encode()

    with pytest.raises(Exception) as excinfo:
        raise Exception(value)
    str(excinfo)


def test_code_getargs() -> None:
    def f1(x):
        raise NotImplementedError()

    c1 = Code.from_function(f1)
    assert c1.getargs(var=True) == ("x",)

    def f2(x, *y):
        raise NotImplementedError()

    c2 = Code.from_function(f2)
    assert c2.getargs(var=True) == ("x", "y")

    def f3(x, **z):
        raise NotImplementedError()

    c3 = Code.from_function(f3)
    assert c3.getargs(var=True) == ("x", "z")

    def f4(x, *y, **z):
        raise NotImplementedError()

    c4 = Code.from_function(f4)
    assert c4.getargs(var=True) == ("x", "y", "z")

    def f5(x, *y, **z):
        a1 = a2 = a3 = a4 = a5 = a6 = 1  # noqa: F841

    c5 = Code.from_function(f5)
    f5(1, 2, 3, z=4)  # cover function body
    assert c5.getargs(var=True) == ("x", "y", "z")

    def f6(x, *y, kw=1, **z):
        a1 = a2 = a3 = a4 = a5 = a6 = 1  # noqa: F841

    c6 = Code.from_function(f6)
    f6(1, 2, kw=3, z=4)  # cover function body
    assert c6.getargs(var=True) == ("x", "kw", "y", "z")


def test_frame_getargs() -> None:
    def f1(x) -> FrameType:
        return sys._getframe(0)

    fr1 = Frame(f1("a"))
    assert fr1.getargs(var=True) == [("x", "a")]

    def f2(x, *y) -> FrameType:
        return sys._getframe(0)

    fr2 = Frame(f2("a", "b", "c"))
    assert fr2.getargs(var=True) == [("x", "a"), ("y", ("b", "c"))]

    def f3(x, **z) -> FrameType:
        return sys._getframe(0)

    fr3 = Frame(f3("a", b="c"))
    assert fr3.getargs(var=True) == [("x", "a"), ("z", {"b": "c"})]

    def f4(x, *y, **z) -> FrameType:
        return sys._getframe(0)

    fr4 = Frame(f4("a", "b", c="d"))
    assert fr4.getargs(var=True) == [("x", "a"), ("y", ("b",)), ("z", {"c": "d"})]


class TestExceptionInfo:
    def test_bad_getsource(self) -> None:
        try:
            if False:
                pass  # type: ignore[unreachable]
            else:
                assert False
        except AssertionError:
            exci = ExceptionInfo.from_current()
        assert exci.getrepr()

    def test_from_current_with_missing(self) -> None:
        with pytest.raises(AssertionError, match="no current exception"):
            ExceptionInfo.from_current()


class TestTracebackEntry:
    def test_getsource(self) -> None:
        try:
            if False:
                pass  # type: ignore[unreachable]
            else:
                assert False
        except AssertionError:
            exci = ExceptionInfo.from_current()
        entry = exci.traceback[0]
        source = entry.getsource()
        assert source is not None
        assert len(source) == 6
        assert "assert False" in source[5]

    def test_tb_entry_str(self):
        try:
            assert False
        except AssertionError:
            exci = ExceptionInfo.from_current()
        pattern = r"  File '.*test_code.py':\d+ in test_tb_entry_str\n  assert False"
        entry = str(exci.traceback[0])
        assert re.match(pattern, entry)


class TestReprFuncArgs:
    def test_not_raise_exception_with_mixed_encoding(self, tw_mock) -> None:
        args = [("unicode_string", "São Paulo"), ("utf8_string", b"S\xc3\xa3o Paulo")]

        r = ReprFuncArgs(args)
        r.toterminal(tw_mock)

        assert (
            tw_mock.lines[0]
            == r"unicode_string = São Paulo, utf8_string = b'S\xc3\xa3o Paulo'"
        )


def test_ExceptionChainRepr():
    """Test ExceptionChainRepr, especially with regard to being hashable."""
    try:
        raise ValueError()
    except ValueError:
        excinfo1 = ExceptionInfo.from_current()
        excinfo2 = ExceptionInfo.from_current()

    repr1 = excinfo1.getrepr()
    repr2 = excinfo2.getrepr()
    assert repr1 != repr2

    assert isinstance(repr1, ExceptionChainRepr)
    assert hash(repr1) != hash(repr2)
    assert repr1 is not excinfo1.getrepr()


def _recurse_with_changing_locals(x: int) -> None:
    _recurse_with_changing_locals(x + 1)


def _recursion_excinfo() -> ExceptionInfo[RecursionError]:
    with pytest.raises(RecursionError) as excinfo:
        _recurse_with_changing_locals(0)
    return excinfo


class TestRecursionTruncation:
    def test_truncates_when_origin_not_found(self) -> None:
        excinfo = _recursion_excinfo()
        tb = excinfo.traceback
        assert tb.recursionindex() is None
        assert len(tb) > 20

        truncated, extraline = ExceptionInfoFormatter()._truncate_recursive_traceback(tb)
        assert list(truncated) == list(tb[:10]) + list(tb[-10:])
        assert extraline == (
            "!!! Recursion error detected, but the origin of the recursion could not be located.\n"
            f"  Displaying first and last 10 stack frames out of {len(tb)}.\n"
            "  Pass `--full-trace` to see all frames."
        )

        rendered = str(excinfo.getrepr())
        assert "the origin of the recursion could not be located" in rendered

    def test_no_truncation_with_full_trace(self) -> None:
        tb = _recursion_excinfo().traceback
        fmt = ExceptionInfoFormatter(tbfilter=False)
        truncated, extraline = fmt._truncate_recursive_traceback(tb)
        assert len(truncated) == len(tb)
        assert extraline is None

    def test_no_truncation_for_short_traceback(self) -> None:
        tb = _recursion_excinfo().traceback[:20]
        truncated, extraline = ExceptionInfoFormatter()._truncate_recursive_traceback(tb)
        assert len(truncated) == 20
        assert extraline is None


def test_statement_linenos_memoized() -> None:
    node = ast.parse("x = 1\n\nif x:\n    y = 2\nelse:\n    y = 3\n")
    first = _statement_linenos(node)
    assert first == [0, 2, 3, 4, 5]
    assert _statement_linenos(node) is first
    assert get_statement_startend2(3, node) == (3, 4)
    assert _statement_linenos(node) is first
