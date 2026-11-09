"""Tests for FormatOptions."""

import pytest

from energyplus_toolkit.input.format_options import FormatOptions


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"leading": -1}, "leading must be at least 0, got -1"),
        ({"indent": -2}, "indent must be at least 0, got -2"),
        ({"comment_column": -1}, "comment_column must be at least 0, got -1"),
        ({"idd_tag_column": 5}, "idd_tag_column must be at least 6, got 5"),
    ],
)
def test_format_options_are_checked(kwargs, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        FormatOptions(**kwargs)
