# We could add a poetry install here

poetry run pylint aons.py
poetry run isort aons.py
poetry run black aons.py
poetry run ruff check aons.py
poetry run mypy aons.py

# We need tests :)
