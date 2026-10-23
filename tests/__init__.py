import os

try:
    from .direct_git import prefer_direct_git
except ModuleNotFoundError as exc:
    # Зеркала пакета tests в тестах пульта собирают только __init__.py и
    # sandbox.py — без этого модуля вставки нет, прочие отказы — наружу.
    if exc.name != "tests.direct_git":
        raise
    DIRECT_GIT_DIR = None
else:
    DIRECT_GIT_DIR = prefer_direct_git(os.environ)
