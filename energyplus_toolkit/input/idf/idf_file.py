import logging
from pathlib import Path

from energyplus_toolkit.input.idd.idd_constants import COMMENT_ONLY_OBJECT_NAME
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idd.idd_object import IddObject
from energyplus_toolkit.input.idf.idf_object import IdfObject, IdfObjectError

LOG = logging.getLogger("IdfFile")


def split_objects_on_one_line(line: str) -> list[str]:
    """Split a line with several objects into one line per object: "A,1;B,2;  ! c" gives ["A,1;", "B,2;  ! c"].

    That's valid IDF (a ';' ends an object), eg two C++ strings concatenated because of a missing comma in a unit test.
    A "!" comment stays on the last line, as does the start of an object that continues on the following lines.
    """
    data, bang, comment = line.partition("!")
    pieces = data.split(";")
    if not "".join(pieces[1:]).strip():  # no ';', or nothing but the comment after the only one
        return [line]
    lines = [piece + ";" for piece in pieces[:-1]]
    tail = pieces[-1]
    if tail.strip():
        lines.append(tail + bang + comment)  # the start of the next object
    else:
        lines[-1] += tail + bang + comment
    return lines


def find_text_outside_fields(text: str) -> str | None:
    """Return the first line with text that IdfFile would silently drop, or None.

    IdfFile only keeps what's before a ',' or ';' (and '!' comments): anything after the last one of a line is lost.
    """
    for line in text.splitlines():
        data = line.split("!", 1)[0]
        if data[max(data.rfind(","), data.rfind(";")) + 1 :].strip():
            return line.strip()
    return None


def count_idf_objects(text: str) -> int:
    """Count IDF objects by counting ';' outside of ``!`` comments."""
    return sum(line.split("!", 1)[0].count(";") for line in text.splitlines())


def find_lost_objects(text: str, idf: "IdfFile") -> str | None:
    """Return why some objects of ``text`` aren't in ``idf`` (eg not in the IDD, so skipped), or None."""
    expected = count_idf_objects(text)
    parsed = sum(1 for obj in idf.objects if obj.idd_object.name != COMMENT_ONLY_OBJECT_NAME)
    if parsed != expected:
        return f"expected {expected} IDF object(s) but parsed {parsed} (check IDD version)"
    return None


class IdfFileError(Exception):
    pass


class IdfFile:
    """An in-memory representation of an EnergyPlus IDF file.

    Backed by an :class:`IddFile` that provides the schema for each object.
    """

    def __init__(self, idd_file: IddFile) -> None:
        self.idd_file: IddFile = idd_file
        self.header: str = ""
        self._objects: list[IdfObject] = []

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str, idd_file: IddFile) -> "IdfFile":
        """Parse an IDF file from *path*."""
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return cls.loads(text, idd_file)

    @classmethod
    def loads(cls, text: str, idd_file: IddFile) -> "IdfFile":
        """Parse an IDF file from a string."""
        idf = cls(idd_file)
        idf._parse(text)
        return idf

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> None:
        """Populate objects by parsing IDF text.

        Algorithm (mirrors OpenStudio's m_load):
        - Accumulate comment-only lines.
        - On a blank line, flush the comment: the very first flush becomes the
          file header; subsequent flushes are prepended to the next object.
        - On a non-comment, non-blank line, start accumulating an object block
          until a line whose data portion ends with ';'.  Then call
          IdfObject.load() with the accumulated text.
        """
        pending_comment: list[str] = []
        object_lines: list[str] = []
        in_object = False
        header_set = False

        # One object per line at most: "Timestep,4;Zone,Z1;" is split in two lines
        raw_lines: list[str] = []
        for text_line in text.splitlines():
            raw_lines.extend(split_objects_on_one_line(text_line))

        for raw_line in raw_lines:
            line = raw_line.strip()

            # ---- blank line ----
            if not line:
                if not in_object and pending_comment:
                    comment_text = "\n".join(pending_comment)
                    if not header_set:
                        self.header = comment_text
                        header_set = True
                        pending_comment = []
                    else:
                        comment_only_idd = self.idd_file.getObject(COMMENT_ONLY_OBJECT_NAME)
                        if comment_only_idd is not None:
                            obj = IdfObject(idd_object=comment_only_idd)
                            obj.comment = comment_text
                            self._objects.append(obj)
                        pending_comment = []
                continue

            # ---- comment-only line ----
            if line.startswith("!"):
                if in_object:
                    # inline / trailing comment — keep it in the object block
                    object_lines.append(raw_line)
                else:
                    pending_comment.append(line)
                continue

            # ---- object content line ----
            if not in_object:
                in_object = True
                header_set = True  # no comment can become the header once an object has started
                # prepend any accumulated preceding comments
                object_lines = list(pending_comment) + [raw_line]
                pending_comment = []
            else:
                object_lines.append(raw_line)

            # check for end-of-object (a ';' appears before any inline '!')
            data_part = line.split("!")[0]
            if ";" in data_part:
                self._finish_object(object_lines)
                object_lines = []
                in_object = False

        # handle any unterminated object at EOF
        if object_lines:
            LOG.warning("Unterminated object at end of file — attempting to parse anyway")
            self._finish_object(object_lines)

        # flush any trailing comments after the last object
        if pending_comment:
            comment_only_idd = self.idd_file.getObject(COMMENT_ONLY_OBJECT_NAME)
            if comment_only_idd is not None:
                obj = IdfObject(idd_object=comment_only_idd)
                obj.comment = "\n".join(pending_comment)
                self._objects.append(obj)

    def _finish_object(self, lines: list[str]) -> None:
        """Parse accumulated lines as one IdfObject and append it."""
        text = "\n".join(lines)

        # peek at the object type (first non-comment token before , or ;)
        object_type: str | None = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") or not stripped:
                continue
            token = stripped.split("!")[0].split(",")[0].split(";")[0].strip()
            if token:
                object_type = token
                break

        if object_type is None:
            LOG.warning("Could not determine object type from block — skipping")
            return

        idd_object: IddObject | None = self.idd_file.getObject(object_type)
        if idd_object is None:
            LOG.warning(f"Unknown object type '{object_type}' — skipping")
            return

        try:
            obj = IdfObject.load(idd_object=idd_object, text=text)
            self._objects.append(obj)
        except IdfObjectError as exc:
            LOG.error(f"Failed to parse object '{object_type}': {exc} — skipping")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def objects(self) -> list[IdfObject]:
        """All objects in the file (in order)."""
        return list(self._objects)

    def num_objects(self) -> int:
        return len(self._objects)

    def get_object(self, index: int) -> IdfObject | None:
        if 0 <= index < len(self._objects):
            return self._objects[index]
        return None

    def get_objects_by_type(self, idd_object: IddObject | str) -> list[IdfObject]:
        """Return all objects whose IDD type matches *idd_object*."""
        name = idd_object if isinstance(idd_object, str) else idd_object.name
        return [o for o in self._objects if o.idd_object.name.lower() == name.lower()]

    def get_objects_by_name(self, name: str) -> list[IdfObject]:
        """Return all objects whose name field equals *name* (case-insensitive)."""
        return [o for o in self._objects if (o.name or "").lower() == name.lower()]

    def num_objects_of_type(self, idd_object: IddObject | str) -> int:
        return len(self.get_objects_by_type(idd_object))

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_object(self, obj: IdfObject) -> None:
        self._objects.append(obj)

    def add_objects(self, objs: list[IdfObject]) -> None:
        for obj in objs:
            self.add_object(obj)

    def remove_object(self, obj: IdfObject) -> bool:
        """Remove *obj* by identity.  Returns True if found and removed."""
        for i, o in enumerate(self._objects):
            if o is obj:
                self._objects.pop(i)
                return True
        return False

    def remove_objects(self, objs: list[IdfObject]) -> int:
        """Remove each object in *objs* by identity.  Returns count removed."""
        return sum(1 for o in objs if self.remove_object(o))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        parts: list[str] = []
        if self.header:
            parts.append(self.header)
            parts.append("")
        for obj in self._objects:
            parts.append(str(obj))
        return "\n".join(parts)

    def save(self, path: Path | str, overwrite: bool = False) -> bool:
        """Write the file to *path*.  Returns True on success."""
        p = Path(path)
        if p.exists() and not overwrite:
            LOG.error(f"File '{p}' already exists and overwrite=False")
            return False
        p.write_text(str(self), encoding="utf-8")
        return True

    def __repr__(self) -> str:
        return f"IdfFile({len(self._objects)} objects)"
