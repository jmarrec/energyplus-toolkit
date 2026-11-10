"""How IDF and IDD files are written: passed down when writing, like black's Mode, instead of module globals."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatOptions:
    # === IDF ===
    # Spaces before the object type line (0 = flush left)
    leading: int = 0
    # Spaces before each field line, after ``leading``
    indent: int = 2
    # Column where the "!-" comment starts (0-based), after ``leading``
    comment_column: int = 27
    # Keep a number written as an integer (eg "8") as an integer in a real field, instead of writing "8.0". EnergyPlus
    # stores "8" as an int and "8.0" as a double, which matters where it reads the field with getIntFieldValue.
    keep_integer_reals: bool = False
    # Real fields (by IDD field name, lowercase) where a number written as an integer is always kept as an integer.
    # "Number of Vertices" is an integer in practice, but can't be \type integer as it's \autocalculatable: EnergyPlus
    # would then parse "4.0" as a double, that the integer type rejects.
    keep_integer_reals_fields: frozenset[str] = frozenset({"number of vertices"})

    # === IDD ===
    # Column where the "\" of IDD field and tag lines starts (0-based): "  A1 , \field", "       \note"
    idd_tag_column: int = 7

    def __post_init__(self) -> None:
        """Checked here, so the library and the command line both get an error rather than a broken layout."""
        for name in ("leading", "indent", "comment_column"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be at least 0, got {getattr(self, name)}")
        # Room for "  A1, ". A longer field id (A10, N100...) still pushes its "\field" past the column: ljust doesn't
        # truncate, as with the default 7 and "  A100, \field"
        if self.idd_tag_column < 6:
            raise ValueError(f"idd_tag_column must be at least 6, got {self.idd_tag_column}")

    @property
    def idf_field_indent(self) -> str:
        """What comes before an IDF field line."""
        return " " * (self.leading + self.indent)

    @property
    def idd_tag_indent(self) -> str:
        """What comes before an IDD tag line ("\\note", "\\type"...)."""
        return " " * self.idd_tag_column

    def keeps_integer(self, field_name: str) -> bool:
        """Whether a number written as an integer stays one in the real IDF field ``field_name``."""
        return self.keep_integer_reals or field_name.lower() in self.keep_integer_reals_fields


DEFAULT_FORMAT_OPTIONS = FormatOptions()
