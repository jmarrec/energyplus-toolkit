import re

RE_VERSION = re.compile(r"^!IDD_Version (\S+)")
RE_BUILD = re.compile(r"^!IDD_BUILD (\S+)")
RE_HEADER = re.compile(r"^(^!.*?^[^!])", re.MULTILINE)
RE_COMMENT_ONLY_LINE = re.compile(r"^[\s\t]*[!](.*)")
RE_CONTENT_AND_COMMENT_LINE = re.compile(r"^([^!]*)[!]?(.*)")
RE_GROUP = re.compile(r"^[\\][gG]roup(.*)")
RE_INCLUDE_FILE = re.compile(r"^[\\][iI]nclude-[fF]ile(.*)")
RE_REMOVE_OBJECT = re.compile(r"^[\\][rR]emove-[oO]bject(.*)")
RE_LINE = re.compile(r"^([^!]*?)[,;](.*)")
RE_MEMO_PROPERTY = re.compile(r"^[mM]emo(.*)")
RE_NOTE_PROPERTY = re.compile(r"^[nN]ote(.*)")
RE_OBJECT_NO_FIELDS = re.compile(r"^([^!^,]*?)[;](.*)")
RE_OBJECT_AND_FIELDS = re.compile(r"^(.*?[,].*?)([AN][0-9]+[\s\t]*[,;].*)")
RE_UNIQUE_PROPERTY = re.compile(r"^[uU]nique-[oO]bject")
RE_REQUIRED_OBJECT_PROPERTY = re.compile(r"^[rR]equired-[oO]bject")
RE_OBSOLETE_PROPERTY = re.compile(r"^[oO]bsolete(.*)")
RE_HASURL_PROPERTY = re.compile(r"^(URL-[Oo]bject|url-[Oo]bject)")
RE_EXTENSIBLE_PROPERTY = re.compile(r"^[eE]xtensible[\s\t]*:[\s\t]*([1-9][0-9]*)")
RE_FORMAT_PROPERTY = re.compile(r"^[fF]ormat([^!]*)")
RE_MIN_FIELDS_PROPERTY = re.compile(r"^[mM]in-[fF]ields[\s\t]*([0-9]+)")
RE_MAX_FIELDS_PROPERTY = re.compile(r"^[mM]ax-[fF]ields[\s\t]*([0-9]+)")
RE_FIELD = re.compile(r"^[\s\t]*?([AN])([0-9]+)[\s\t]*[,;](.*)")
RE_FIELD_START = re.compile(r"[AN][0-9]+\s*[,;]")
RE_CLOSING_FIELD = re.compile(r"(.*)([AN][0-9]+[\s\t]*[;].*?)$")
RE_LAST_FIELD = re.compile(r"(.*)([AN][0-9]+[\s\t]*[,;].*)$")
RE_NAME = re.compile(r"[\\][fF]ield([^\\^!]*)")
RE_NAME_PROPERTY = re.compile(r"^[fF]ield([^!]*)")
RE_REQUIRED_FIELD_PROPERTY = re.compile(r"^[rR]equired-[fF]ield")
RE_AUTOSIZABLE_PROPERTY = re.compile(r"^[aA]utosizable")
RE_AUTOCALCULATABLE_PROPERTY = re.compile(r"^[aA]utocalculatable")
RE_RETAINCASE_PROPERTY = re.compile(r"^[rR]etaincase")
RE_UNITS_PROPERTY = re.compile(r"^[uU]nits([^!]*)")
RE_IP_UNITS_PROPERTY = re.compile(r"^[iI][pP]-[uU]nits([^!]*)")
RE_MIN_EXCLUSIVE_PROPERTY = re.compile(r"^[mM]inimum[\s\t]*[>]([^!]*)")
RE_MIN_INCLUSIVE_PROPERTY = re.compile(r"^[mM]inimum([^>!]*)")
RE_MAX_EXCLUSIVE_PROPERTY = re.compile(r"^[mM]aximum[\s\t]*[<]([^!]*)")
RE_MAX_INCLUSIVE_PROPERTY = re.compile(r"^[mM]aximum([^<!]*)")
RE_DEPRECATED_PROPERTY = re.compile(r"^[dD]eprecated(.*)")
RE_DEFAULT_PROPERTY = re.compile(r"^[dD]efault([^!]*)")
RE_AUTOMATIC_DEFAULT = re.compile(r".*(autocalculate|autosize).*", re.IGNORECASE)
RE_TYPE_PROPERTY = re.compile(
    r"^type[\s\t]*(integer|real|alpha|choice|node|object-list|external-list|url|handle)",
    re.IGNORECASE,
)
RE_KEY_PROPERTY = re.compile(r"^[kK]ey(.*)")
RE_OBJECT_LIST_PROPERTY = re.compile(r"^[oO]bject-[lL]ist([^!]*)")
RE_EXTERNAL_LIST_PROPERTY = re.compile(r"^[eE]xternal-[lL]ist([^!]*)")
RE_REFERENCE_PROPERTY = re.compile(r"^[rR]eference([^!]*)")
RE_REFERENCE_CLASS_NAME_PROPERTY = re.compile(r"^[rR]eference-[cC]lass-[nN]ame([^!]*)")
RE_BEGIN_EXTENSIBLE = re.compile(r"[\\][bB]egin-[eE]xtensible")
RE_BEGIN_EXTENSIBLE_PROPERTY = re.compile(r"^[bB]egin-[eE]xtensible")
RE_METADATA_COMMENT = re.compile(r"^[\s\t]*?[\\]([^\\]*)(.*)")
RE_VERSION_OBJECT_NAME = re.compile(r".*[vV]ersion.*")
# The group number in an extensible field name: the last standalone number, eg "1" in "Vertex 1 X-coordinate" or in
# "2017 Speed 1 Rated Evaporator Fan Power Per Volume Flow Rate"
RE_GROUP_NUMBER = re.compile(r"\b[0-9]+\b(?!.*\b[0-9]+\b)")

#######################################################################################################################
#                                             C O M M E N T    R E G E X                                              #
#######################################################################################################################

# Matches lines containing only horizontal whitespace
RE_WHITESPACE_ONLY_LINE: re.Pattern = re.compile(r"^[ \t]*$")

# Matches lines containing optional comment starting with '!'
RE_COMMENT_WHITESPACE_ONLY_LINE: re.Pattern = re.compile(r"^[ \t]*(?:!([^\n\r\v]*))?$")

# Matches lines containing optional editor comment starting with '!-'
RE_EDITOR_COMMENT_WHITESPACE_ONLY_LINE: re.Pattern = re.compile(r"^[ \t]*(?:!-([^\n\r\v]*))?$")

# Matches any block of whitespace
RE_WHITESPACE_ONLY_BLOCK: re.Pattern = re.compile(r"[\s]*")

# Matches a block of lines that may contain comments starting with '!'
RE_COMMENT_WHITESPACE_ONLY_BLOCK: re.Pattern = re.compile(r"(?:^[ \t]*(?:![^\v\n]*)?[\v\n]?)*")

# Matches a block of lines that may contain editor comments starting with '!-'
RE_EDITOR_COMMENT_WHITESPACE_ONLY_BLOCK: re.Pattern = re.compile(r"(?:^[ \t]*(?:!-[^\v\n]*)?[\v\n]?)*")
