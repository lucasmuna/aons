# We could add a poetry install here
BANNER=------------------------------------------------------------------

echo poetry
echo $BANNER
poetry install --with dev
echo
echo pylint
echo $BANNER
poetry run pylint aons.py
echo
echo isort
echo $BANNER
poetry run isort aons.py
echo
echo black
echo $BANNER
poetry run black aons.py
echo
echo ruff
echo $BANNER
poetry run ruff check aons.py
echo
echo mypy
echo $BANNER
poetry run mypy aons.py

# We need tests :)
