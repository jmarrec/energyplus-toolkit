import re

# Match a new line
RE_NEW_LINE_STRING = re.compile(r"\n")

# Match an optional new line
# matches[1]: before new line and new line
# matches[2]: after new line
OPTIONAL_NEW_LINE_PATTERN = r"([^\n]*\n?)(.*)"
RE_OPTIONAL_NEW_LINE_STRING = re.compile(OPTIONAL_NEW_LINE_PATTERN)

# Match comment only line
# matches[1]: the comment
# matches[2]: after new line
RE_COMMENT_ONLY_LINE = re.compile(r"^[\s\t]*[!]([^\n]*)[\n]?(.*)")

# Match content and comment
# matches[1]: the content
# matches[2]: the comment
RE_CONTENT_AND_COMMENT_LINE = re.compile(r"^([^!,;]*)[,;]?[\s\t]*[!]?(.*)")

# Match object end in the idf
RE_OBJECT_END = re.compile(r"^[^!]*?[;].*")

# Match line with an object type and name
# matches[1]: before first separator
# matches[2]: after first separator and before second separator
RE_OBJECT_TYPE_AND_NAME = re.compile(r"^([^!]*?)[,;]([^!]*?)[,;]")

# Match line with either a ',' or a ';' that are not preceded by '!'
# matches[1]: before separator
# matches[2]: after separator and before new line
# matches[3]: after new line
RE_LINE = re.compile(rf"^([^!]*?)[,;]{OPTIONAL_NEW_LINE_PATTERN}")

# Match an autosize field
RE_AUTOSIZE = re.compile(r"autosize", re.IGNORECASE)

# Match an autocalculate field
RE_AUTOCALCULATE = re.compile(r"autocalculate", re.IGNORECASE)

# Match line with '##def SomeSection[]' preceded only by whitespace
# matches[1]: the imf section name (e.g. 'SomeSection')
# matches[2]: inside the [] brackets
RE_IMF_SECTION = re.compile(r"^[\s\t]*##[\s\t]*def[\s\t]*(.*?)\[(.*?)\]")

# Match line with '##enddef' preceded and followed only by whitespace
RE_IMF_SECTION_END = re.compile(r"^[\s\t]*##[\s\t]*enddef[\s\t]*")
