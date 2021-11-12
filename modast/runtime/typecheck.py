"""
This is the runtime for the typechecker.

Currently does not support any "types" in the `typing` module.
Only actual `type` objects are supported.
Python does not provide any help to do type-checks on `typing`'s "type".
"""

import sys


class TypecheckError(TypeError):
    pass


def typecheck_arg(name, value, expected_type, /):
    _typecheck(value, expected_type, f"argument {name!r}")


def typecheck_assign(name, value, expected_type, /):
    _typecheck(value, expected_type, f"variable {name!r}")
    return value


def typecheck_return(value, expected_type, /):
    _typecheck(value, expected_type, f"return value")
    return value


def _typecheck(value, expected_type, message, /):
    # resolve forward reference
    if isinstance(expected_type, str):

        pathitems = expected_type.split(".")
        # lookup global name in parent frame
        # NOTE: avoid cyclic reference to frame
        try:
            obj = sys._getframe(2).f_globals[pathitems[0]]
        except KeyError:
            # bypass error
            return
        else:
            for sub in pathitems[1:]:
                obj = getattr(obj, sub)
            expected_type = obj

    if isinstance(expected_type, type):
        if not isinstance(value, expected_type):
            got_type = type(value)
            raise TypecheckError(
                f"invalid {message}\n"
                f"  expect: {expected_type.__qualname__:20} ({expected_type.__module__})\n"
                f"     got: {got_type.__qualname__:20} ({got_type.__module__})"
            )
