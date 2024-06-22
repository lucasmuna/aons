import pathlib
from pprint import pprint as print

import aons

aons_data_file = pathlib.Path(__file__).parent / "data.aons"
aons_schema_file = pathlib.Path(__file__).parent / "schema.aons"

aons_data = aons.AonsData(aons_data_file)
aons_schema = aons.AonsSchema(aons_data_file)

print(aons_data.get_dict())
aons_data.get_dict_with_comments()

aons_schema.get_dict()
aons_schema.get_dict_with_comments()
