import pathlib
# from pprint import pprint as print

import aons

aons_data_file = pathlib.Path(__file__).parent / "data.aons"
aons_compliant_data_file = pathlib.Path(__file__).parent / "compliant_data.aons"
aons_additional_data_file = pathlib.Path(__file__).parent / "additional_data.aons"
aons_missing_required_data_file = (
    pathlib.Path(__file__).parent / "missing_required_data.aons"
)
aons_schema_file = pathlib.Path(__file__).parent / "schema.aons"

aons_data = aons.load(aons_data_file)
aons_compliant_data = aons.load(aons_compliant_data_file)
aons_additional_data = aons.load(aons_additional_data_file)
aons_missing_required_data = aons.load(aons_missing_required_data_file)
aons_schema = aons.load(aons_schema_file)

# print: show case data get_dict and get_dict_with_comments
(aons_data.get_dict())
(aons_data.get_dict_with_comments())
(aons_data.get_dict_with_comments()["main"]["__value__"]["my_string"]["__comment__"])

# print: show case schema get_dict and get_dict_with_comments
(aons_schema.get_dict())
(aons_schema.get_dict_with_comments())

# print: show case dict like __getitem__ and __setitem__
(aons_data["my_list_int"][0])
aons_data["my_list_int"][0] = 1
(aons_data["my_list_int"][0])

# print: show case validation of a data against a schema (default, enums, required, etc)
(aons_compliant_data.get_dict())
aons_validated_data = aons.validate(aons_compliant_data, aons_schema)
(aons_validated_data.get_dict())
aons_validated_data["my_list"] = [1]
(aons_validated_data["my_list"])
(aons_schema["parameters"]["my_list"]["default"])


# print: show case validation for additional and missing required
try:
    aons.validate(aons_additional_data, aons_schema)
    assert False
except Exception as exception:
    (exception)
    assert type(exception) == aons.AonsAdditionalItems
try:
    aons.validate(aons_missing_required_data, aons_schema)
    assert False
except Exception as exception:
    (exception)
    assert type(exception) == aons.AonsMissingRequiredItem

(aons.dumps(aons_data))
