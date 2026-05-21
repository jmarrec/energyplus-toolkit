# IDF_LEADING: leading spaces before the object-type name line (0 = flush left).
IDF_LEADING = 0
# IDF_INDENT: leading spaces before each field-value line.
IDF_INDENT = 2
# Column at which the "!-" comment begins (0-based).
IDF_COMMENT_COLUMN = 27


def format_idf_field(
    value: str, is_last_field: bool, field_name: str, comment: str | None = None, units: str | None = None
) -> str:
    """Serialize one IDF field value line.

    The indent is ``IDF_LEADING + IDF_INDENT`` spaces.  The value and its
    separator are then padded so that the ``!-`` comment starts at
    ``IDF_COMMENT_COLUMN + IDF_LEADING``.  When the value is too long to fit,
    a minimum of two spaces are inserted between the separator and the comment.

    Examples (IDF_LEADING=0, IDF_INDENT=2, IDF_COMMENT_COLUMN=27)::

        format_idf_field("No", False, "Do Zone Sizing Calculation")
        # "  No,                      !- Do Zone Sizing Calculation"

        format_idf_field("Simple One Zone (Wireframe DXF)", False, "Name")
        # "  Simple One Zone (Wireframe DXF),  !- Name"

    With IDF_LEADING=2 the same call produces::

        # "    No,                      !- Do Zone Sizing Calculation"
    """
    sep = ";" if is_last_field else ","
    indent = IDF_LEADING + IDF_INDENT
    # IDF_LEADING cancels in the padding formula, so comment column relative to
    # the value start is always IDF_COMMENT_COLUMN - IDF_INDENT.
    padding = max(2, IDF_COMMENT_COLUMN - IDF_INDENT - len(value) - 1)
    if comment is not None:
        return f"{' ' * indent}{value}{sep}{' ' * padding}! {comment}"
    line = f"{' ' * indent}{value}{sep}{' ' * padding}!- {field_name}"
    if units:
        line += f" {{{units}}}"
    return line
