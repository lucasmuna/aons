"""Another Object Notation Syntax."""

import abc
import ast
import dataclasses
import pathlib
import token
import tokenize
from typing import Any, Iterator, Literal, cast, get_args

_KeyLiteralTypes = Literal["str", "object", "list", "int", "float", "number", "boolean"]


class AonsFileWithoutMainElement(Exception):
    """This exception indicates that the given AONS file doesn't have a main element."""


class AonsUnknownKeyType(Exception):
    """This exception indicates that a unkown Key type was found."""


class AonsWrongEncoding(Exception):
    """This exception indicates that the given AONS file is not UTF-8 encoded."""


class AonsContentLineNotEndedWithComma(Exception):
    """This exception indicates that a content line of an AONS file doesn't end with a comma."""


class AonsKeyNotFollowedWithColon(Exception):
    """This exception indicates that a key of an AONS file isn't followed by a colon."""


@dataclasses.dataclass
class _Comment:
    value: str = ""

    @classmethod
    def from_token(cls, token_info: tokenize.TokenInfo):
        """Creates a class instance out of a token_info."""
        return cls(value=token_info.string)


@dataclasses.dataclass
class _Key(abc.ABC):
    name: str | None
    value: Any
    comment: str | None = None

    @classmethod
    def from_token_info_and_iterator(
        cls,
        token_info: tokenize.TokenInfo,
        token_it: Iterator[tokenize.TokenInfo],
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
            return _KeySingle.from_name_value_and_token_iterator(name, value, token_it)
        if token_info.type == token.OP and token_info.string == "{":
            return _KeyObject.from_name_and_token_iterator(name, token_it)
        if token_info.type == token.OP and token_info.string == "[":
            return _KeyList.from_name_and_token_iterator(name, token_it)
        if token_info.type == token.COMMENT:
            return _Comment.from_token(token_info)
        return None

    # We have to have separate impl for single list and dict
    def __getitem__(self, key):
        return self.value[key]

    def __setitem__(self, key, value):
        self.value[key].value = value

    @abc.abstractmethod
    def get_dict(self) -> Any:  # We should probably change this method name
        """Returns a dictionary containing the respective instance data."""

    def _dict_with_comments_template(self, value: Any):
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
        cls, name: str, value: Any, token_it: Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name, value and a token iterator."""
        token_type = cast(_KeyLiteralTypes, type(ast.literal_eval(value)).__name__)
        if token_type not in get_args(_KeyLiteralTypes):
            raise TypeError
        token_info = next(token_it)
        if token_info.type != token.OP and token_info.string != ",":
            raise AonsContentLineNotEndedWithComma
        if token_type == "str":
            return _KeyString(name, value)
        if token_type == "float":
            return _KeyFloat(name, value)
        if token_type == "int":
            return _KeyInteger(name, value)
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
    value: dict[str, Any]

    @classmethod
    def from_name_and_token_iterator(
        cls, name: str | None, token_it: Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name and a token iterator."""
        last_key_name: str = ""
        key_dict: dict[str, Any] = {}
        comment: list[str] = []
        for token_info in token_it:
            if token_info.type == token.OP and token_info.string == "}":
                token_info = next(token_it)
                if token_info.type != token.OP and token_info.string != ",":
                    raise AonsContentLineNotEndedWithComma
                return cls(name, key_dict, comment="\n".join(comment))
            if key := _Key.from_token_info_and_iterator(token_info, token_it):
                if isinstance(key, _Comment):
                    if last_key_name:
                        key_dict[last_key_name].comment = key.value
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
        cls, name: str | None, token_it: Iterator[tokenize.TokenInfo]
    ):
        """Creates a class instance out of a name and a token iterator."""
        value_list: list[_Key] = []
        comment: list[str] = []
        for token_info in token_it:
            if token_info.type == token.OP and token_info.string == "]":
                token_info = next(token_it)
                if token_info.type != token.OP and token_info.string != ",":
                    raise AonsContentLineNotEndedWithComma
                return cls(name, value_list, comment="\n".join(comment))
            if value := _Key.from_token_info_and_iterator(token_info, token_it):
                if isinstance(value, _Comment):
                    if value_list:
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


class Aons:
    """Representation of an AONS object."""

    def __init__(self):
        self._encoding = None
        self._entries = None

    @classmethod
    def from_file(cls, file: pathlib.Path):
        """Create and return an AONS instance from a given file."""
        instance = cls()
        with file.open("rb") as stream:
            token_iterator = tokenize.tokenize(stream.readline)
            instance._encoding = instance._get_encoding(token_iterator)
            instance._entries = instance._get_entries(token_iterator)
        return instance

    @staticmethod
    def _get_encoding(token_iterator) -> str:
        """Get AONS file enconding from the first token."""
        fisrt_token = next(token_iterator)
        encoding = fisrt_token.string
        if fisrt_token.type != token.ENCODING or encoding != "utf-8":
            raise AonsWrongEncoding
        return encoding

    @staticmethod
    def _get_entries(token_iterator):
        """Iterates through the loaded tokens and returns a dictionary containing every entry."""
        for token_info in token_iterator:
            if token_info.type == token.OP and token_info.string == "{":
                return _KeyObject.from_name_and_token_iterator(None, token_iterator)
            if token_info.type == token.OP and token_info.string == "[":
                return _KeyList.from_name_and_token_iterator(None, token_iterator)
        raise AonsFileWithoutMainElement

    def __getitem__(self, key):
        return self._entries.value[key]

    def __setitem__(self, key, value):
        self._entries.value[key].value = value

    def get_dict(self) -> dict:
        """Returns a dictionary containing data from every entry."""
        return self._entries.get_dict()

    def get_dict_with_comments(self) -> dict:
        """Returns a dictionary containing data and comments from every entry.

        The user should expect an additional layer of keys to the dictionary in order to
         incorporate both data and comments.
        """
        return self._entries.get_dict_with_comment()


def load(file: pathlib.Path) -> Aons:
    """Load an AONS file from a given path and return an Aons class instance."""
    return Aons.from_file(file)


def validate(data: Aons, schema: Aons):
    """Validate a given data against a given schema, both being Aons instances."""
    raise NotImplementedError
    # data = data.get_dict()
    # schema = schema.get_dict()
