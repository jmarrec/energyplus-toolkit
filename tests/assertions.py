import pytest

from energyplus_parser.idf.idf_field import IdfField


class MethodCheckerError(Exception):
    pass


def object_format(obj) -> str:
    if isinstance(obj, IdfField):
        default_attr = " [defaulted]" if obj.is_defaulted() else ""
        return f"{obj.__class__.__name__} '{obj.idd_field.name}' ({obj.value(return_default=True)}{default_attr})"
    else:
        return f"Object {obj!r}"


def assert_has_method(obj, method_name: str):
    if not hasattr(obj, method_name):
        raise MethodCheckerError(f"{object_format(obj=obj)} does not have attribute '{method_name}'.")
    # assert hasattr(obj, method_name), f"{object_format(obj=obj)} does not have attribute '{method_name}'."
    method = getattr(obj, method_name)
    is_callable = callable(method)
    if not is_callable:
        raise MethodCheckerError(f"{object_format(obj=obj)} has attribute '{method_name}' but it is not callable.")
    # assert is_callable, f"{object_format(obj=obj)} has attribute '{method_name}' but it is not callable."


def refute_has_method(obj, method_name: str):
    if hasattr(obj, method_name):
        method = getattr(obj, method_name)
        is_callable = callable(method)
        if is_callable:
            raise MethodCheckerError(
                f"{object_format(obj=obj)} has callable method '{method_name}', but it should not."
            )
        else:
            raise MethodCheckerError(f"{object_format(obj=obj)} has non-callable attribute '{method_name}'.")
