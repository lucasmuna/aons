"""Another Object Notation Syntax."""

import abc
import ast
import copy
import dataclasses
import pathlib
import token
import tokenize
import typing as t

_KeyLiteralTypes = t.Literal[
    "str", "object", "list", "int", "float", "number", "boolean"
]


class AonsFileWithoutMainElement(Exception):
    """The given AONS file doesn't have a main element."""


class AonsFileWithDuplicatetMainElement(Exception):
    """The given AONS file has two or more main elements."""


class AonsFileWrongMainElement(Exception):
    """The given AONS file has wrong main element type."""


class AonsUnknownKeyType(Exception):
    """An unkown Key type was found."""


class AonsWrongEncoding(Exception):
    """The given AONS file is not UTF-8 encoded."""


class AonsContentLineNotEndedWithComma(Exception):
    """A content line of an AONS file doesn't end with a comma."""


class AonsKeyNotFollowedWithColon(Exception):
    """A key of an AONS file isn't followed by a colon."""


class AonsSchemaFileNotDict(Exception):
    """The given AONS schema is not a dict."""


class AonsSchemaInvalidElement(Exception):
    """The given AONS schema has an invalid element."""


class AonsMissingRequiredItem(Exception):
    """A given AONS data is missing required item(s) from a given AONS schema."""


class AonsAdditionalItems(Exception):
    """A given AONS data has additional item(s) than a given AONS schema."""


class AonsValueNotAllowed(Exception):
    """A given AONS item was not found in a given AONS schema enumeration."""


class AonsWrontTypeMatching(Exception):
    """A given AONS data type doesn't match a given AONS schema type."""


@dataclasses.dataclass
class _Item:
    value: t.Any


@dataclasses.dataclass
class _Items(list[_Item]): ...


@dataclasses.dataclass
class _Comment(_Item):
    value: str = ""

    @classmethod
    def from_token(cls, token_info: tokenize.TokenInfo):
        """Creates a class instance out of a token_info."""
        return cls(value=token_info.string)


@dataclasses.dataclass
class Key(_Item):
    """Interface to a common Key."""

    name: str
    comment: str = ""

    # We have to have separate impl for single list and dict
    def __getitem__(self, key):
        return self.value[key]

    def __setitem__(self, key, value):
        self.value[key].value = value


@dataclasses.dataclass
class _Key(Key, abc.ABC):

    @classmethod
    def from_token_info_and_iterator(
        cls,
        token_info: tokenize.TokenInfo,
        token_it: t.Iterator[tokenize.TokenInfo],
    ):
        """Creates a class instance out of a given token info and its iterator."""
        name = ""
        if token_info.type == token.NAME:
            name = token_info.string
            token_info = next(token_it)
            if token_info.type != token.OP or token_info.string != ":":
                raise AonsKeyNotFollowedWithColon
            token_info = next(token_it)
        if token_info.type in [token.STRING, token.NUMBER]:
            value = token_info.string
            return _KeySingle.from_name_value_and_token_iterator(
                name=name, value=value, token_it=token_it
            )
        if token_info.type == token.OP and token_info.string == "{":
            return _KeyObject.from_name_and_token_iterator(name=name, token_it=token_it)
        if token_info.type == token.OP and token_info.string == "[":
            return _KeyList.from_name_and_token_iterator(name=name, token_it=token_it)
        if token_info.type == token.COMMENT:
            return _Comment.from_token(token_info=token_info)
        return None

    @abc.abstractmethod
    def get_dict(self) -> t.Any:  # We should probably change this method name
        """Returns a dictionary containing the respective instance data."""

    def _dict_with_comments_template(self, value: t.Any):
        return {"__comment__": self.comment, "__value__": value}

    @abc.abstractmethod
    def get_dict_with_comment(self) -> dict:
        """Returns a dictionary containing the respective instance data and comments.

        Concrete implementation of this method are supposed to add an additional layer of keys to
         the dictionary in order to incorporate both data and comments. The default way to do that
         is using _dict_with_comments_template.
        """


@dataclasses.dataclass
class _KeySingle(_Key):
    @classmethod
    def from_name_value_and_token_iterator(
        cls, name: str, value: t.Any, token_it: t.Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name, value and a token iterator."""
        token_type = t.cast(_KeyLiteralTypes, type(ast.literal_eval(value)).__name__)
        if token_type not in t.get_args(_KeyLiteralTypes):
            raise TypeError
        token_info = next(token_it)
        if token_info.type != token.OP and token_info.string != ",":
            raise AonsContentLineNotEndedWithComma
        if token_type == "str":
            return _KeyString(name=name, value=value)
        if token_type == "float":
            return _KeyFloat(name=name, value=value)
        if token_type == "int":
            return _KeyInteger(name=name, value=value)
        raise AonsUnknownKeyType

    def get_dict(self) -> dict:
        """Concrete implementation of _Key.get_dict."""
        return self.value

    def get_dict_with_comment(self) -> dict:
        """Concrete implementation of _Key.get_dict_with_comment."""
        return self._dict_with_comments_template(value=self.value)


@dataclasses.dataclass
class _KeyInteger(_KeySingle):
    value: int

    def __post_init__(self):
        self.value = int(self.value)


@dataclasses.dataclass
class _KeyFloat(_KeySingle):
    value: float

    def __post_init__(self):
        self.value = float(self.value)


@dataclasses.dataclass
class _KeyString(_KeySingle):
    value: str

    def __post_init__(self):
        assert self.value[0] in ['"', "'"]
        assert self.value[-1] in ['"', "'"]
        self.value = self.value[1:-1]


@dataclasses.dataclass
class _KeyObject(_Key):
    value: dict[str, t.Any]

    @classmethod
    def from_name_and_token_iterator(
        cls, name: str, token_it: t.Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name and a token iterator."""
        last_key_name: str = ""
        key_dict: dict[str, t.Any] = {}
        comment: list[str] = []
        for token_info in token_it:
            if token_info.type == token.OP and token_info.string == "}":
                token_info = next(token_it)
                if token_info.type != token.OP and token_info.string != ",":
                    raise AonsContentLineNotEndedWithComma
                return cls(name=name, value=key_dict, comment="\n".join(comment))
            if key := _Key.from_token_info_and_iterator(token_info, token_it):
                if isinstance(key, _Comment):
                    if last_key_name:
                        if key_dict[last_key_name].comment:
                            key_dict[last_key_name].comment += "\n"
                        key_dict[last_key_name].comment += key.value
                    else:
                        comment.append(key.value)
                else:
                    key_dict[key.name] = key
                    last_key_name = key.name
        raise AonsFileWithoutMainElement

    def get_dict(self) -> dict:
        """Concrete implementation of _Key.get_dict."""
        return {key: value.get_dict() for key, value in self.value.items()}

    def get_dict_with_comment(self) -> dict:
        """Concrete implementation of _Key.get_dict_with_comment."""
        return self._dict_with_comments_template(
            value={
                key: item.get_dict_with_comment() for key, item in self.value.items()
            }
        )


@dataclasses.dataclass
class _KeyList(_Key):
    value: list[_Key]

    @classmethod
    def from_name_and_token_iterator(
        cls, name: str, token_it: t.Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name and a token iterator."""
        value_list: list[_Key] = []
        comment: list[str] = []
        for token_info in token_it:
            if token_info.type == token.OP and token_info.string == "]":
                token_info = next(token_it)
                if token_info.type != token.OP and token_info.string != ",":
                    raise AonsContentLineNotEndedWithComma
                return cls(name=name, value=value_list, comment="\n".join(comment))
            if value := _Key.from_token_info_and_iterator(token_info, token_it):
                if isinstance(value, _Comment):
                    if value_list:
                        if value_list[-1].comment:
                            value_list[-1].comment += "\n"
                        value_list[-1].comment = value.value
                    else:
                        comment.append(value.value)
                else:
                    value_list.append(value)
        raise AonsFileWithoutMainElement

    def get_dict(self) -> list:
        """Concrete implementation of _Key.get_dict."""
        return [value.get_dict() for value in self.value]

    def get_dict_with_comment(self) -> dict:
        """Concrete implementation of _Key.get_dict_with_comment."""
        return self._dict_with_comments_template(
            value=[value.get_dict_with_comment() for value in self.value]
        )


@dataclasses.dataclass
class _Entries:
    main: _Key
    pre: _Items
    pos: _Items


class Aons:
    """Representation of an AONS object."""

    def __init__(self, encoding: str, entries: _Entries):
        self._encoding: str = encoding
        self._entries: _Entries = entries

    @classmethod
    def from_file(cls, file: pathlib.Path):
        """Create and return an AONS instance from a given file."""
        with file.open("rb") as stream:
            token_iterator = tokenize.tokenize(stream.readline)
            encoding = cls._get_encoding(token_iterator)
            entries = cls._get_entries(token_iterator)
        return cls(encoding=encoding, entries=entries)

    @staticmethod
    def _get_encoding(token_iterator) -> str:
        """Get AONS file enconding from the first token."""
        fisrt_token = next(token_iterator)
        encoding = fisrt_token.string
        if fisrt_token.type != token.ENCODING or encoding != "utf-8":
            raise AonsWrongEncoding
        return encoding

    @staticmethod
    def _get_entries(token_iterator) -> _Entries:
        """Iterates through the loaded tokens and returns a dictionary containing every entry."""
        main: _Key | None = None
        pre = _Items()
        pos = _Items()
        for token_info in token_iterator:
            key = _Key.from_token_info_and_iterator(token_info, token_iterator)
            if isinstance(key, (_KeyObject, _KeyList)):
                if main:
                    raise AonsFileWithDuplicatetMainElement
                main = key
            elif isinstance(key, _KeySingle):
                raise AonsFileWrongMainElement
            elif isinstance(key, _Comment):
                if not main:
                    pre.append(key)
                else:
                    pos.append(key)
        if not main:
            raise AonsFileWithoutMainElement
        return _Entries(main, pre, pos)

    def __getitem__(self, key):
        return self._entries.main.value[key]

    def __setitem__(self, key, value):
        self._entries.main.value[key].value = value

    def get_dict(self) -> dict:
        """Returns a dictionary containing data from every entry."""
        return self._entries.main.get_dict()

    def get_dict_with_comments(self) -> dict:
        """Returns a dictionary containing data and comments from every entry.

        The user should expect an additional layer of keys to the dictionary in order to
         incorporate both data and comments.
        """

        def get_items(items: list[_Item]) -> list[str | dict]:
            return [
                (
                    item.get_dict_with_comment()
                    if hasattr(item, "get_dict_with_comment")
                    else item.value
                )
                for item in items
            ]

        entries = {
            "pre": get_items(self._entries.pre),
            "main": self._entries.main.get_dict_with_comment(),
            "pos": get_items(self._entries.pos),
        }

        # We should not return entries but only main.
        # We could maybe offer more methods to get comments or future anchors.
        return entries


def load(file: pathlib.Path) -> Aons:
    """Load an AONS file from a given path and return an Aons class instance."""
    return Aons.from_file(file)


class _SchemaVisitor:

    @staticmethod
    def get_default(element: _KeyObject) -> dict[str, t.Any]:
        """Returns every item that has a default value from a given elemenet."""
        item_object = element.value["parameters"].value
        return {
            item: item_object[item].value["default"]
            for item in item_object
            if "default" in item_object[item].value
        }

    @staticmethod
    def get_required(element: _KeyObject) -> list[str]:
        """Returns the required items of a given element."""
        if "required" not in element.value:
            return []
        return [item.value for item in element.value["required"]]

    @staticmethod
    def get_enum(element: _KeyObject) -> list[t.Any]:
        """Returns the enumaration of allowed values from a given element."""
        if "enum" not in element.value:
            return []
        return element.value["enum"]


def validate(data: Aons, schema: Aons) -> Aons:
    """Validate a given data against a given schema, both being Aons instances."""
    data_deep_copy = copy.deepcopy(data)

    data_object = data_deep_copy._entries.main
    schema_object = schema._entries.main

    if not isinstance(schema_object, _KeyObject):
        raise AonsSchemaFileNotDict

    def validate_item(data_object: _Key, schema_object: _Key) -> bool:
        default_items = {}
        missing_items = []
        additional_items = []
        # if type(data_object) != type(schema_object):
        #     # TODO: Add type matching, need to get type from schema
        #     raise AonsWrontTypeMatching(type(data_object), type(schema_object))
        if isinstance(data_object, _KeyObject):
            if "parameters" not in schema_object.value:
                raise AonsSchemaInvalidElement
            default_items = _SchemaVisitor.get_default(schema_object)
            missing_items = _SchemaVisitor.get_required(schema_object)
            for item in data_object.value:
                if item in missing_items:
                    missing_items.pop(missing_items.index(item))
                if item in default_items:
                    default_items.pop(item)
                if item not in schema_object.value["parameters"].value:
                    additional_items.append(item)
            if missing_items:
                raise AonsMissingRequiredItem(missing_items)
            if additional_items:
                raise AonsAdditionalItems(additional_items)
            for item in data_object.value:
                validate_item(
                    data_object[item],
                    schema_object.value["parameters"][item],
                )
            if default_items:
                for item in default_items:
                    data_object.value[item] = copy.deepcopy(default_items[item])
        if isinstance(data_object, _KeySingle):
            if enum := _SchemaVisitor.get_enum(schema_object):
                if data_object.value not in enum.get_dict():
                    raise AonsValueNotAllowed

        return True

    validate_item(data_object, schema_object)

    return data_deep_copy
