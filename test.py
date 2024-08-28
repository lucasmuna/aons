import pathlib
from pprint import pprint as print

import aons

aons_data_file = pathlib.Path(__file__).parent / "data.aons"
aons_schema_file = pathlib.Path(__file__).parent / "schema.aons"

aons_data = aons.AonsData.from_file(aons_data_file)
aons_schema = aons.AonsSchema.from_file(aons_schema_file)

# print
(aons_data.get_dict())
(aons_data.get_dict_with_comments())

# print
(aons_schema.get_dict())
(aons_schema.get_dict_with_comments())

print(aons_data["my_list_int"][0])
aons_data["my_list_int"][0] = 1
print(aons_data["my_list_int"][0])

# aons.load(aons_data_file)

# aons.validate(aons_data, aons_schema)
