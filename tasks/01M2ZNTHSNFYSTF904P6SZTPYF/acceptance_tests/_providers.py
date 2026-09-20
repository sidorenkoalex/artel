"""Общий код планки: доступ к пакету провайдеров исполнителя роли без
предположений о форме реестра и о типах возврата методов интерфейса.

Не тестовый модуль (имя с подчёркивания — единственная легитимная форма
общего кода планки, скил test-authoring). Критерии приёмки называют
СОСТАВ интерфейса и факт регистрации имени `claude`, но не форму
зарегистрированного объекта (класс, экземпляр, модуль, фабрика) и не тип
возврата `cli_tool()`/`home_reference()`. Разбор этих форм собран здесь
одним местом, чтобы файлы планки читали их одинаково, а не каждый по
своей догадке.
"""
import importlib
import types
from pathlib import Path

PACKAGE = "orchestrator.providers"
BASE_MODULE = PACKAGE + ".base"
CLAUDE_MODULE = PACKAGE + ".claude"
CLAUDE = "claude"

# Состав интерфейса (AC-1): имя метода -> обязательные имена параметров.
INTERFACE_METHODS = {
    "command": ("model",),
    "environment": ("role", "task_id"),
    "home_reference": (),
    "preflight": ("role",),
    "cli_tool": (),
    "model_verdict": ("model",),
}


def package():
    """Пакет `orchestrator/providers/`."""
    return importlib.import_module(PACKAGE)


def base_module():
    """Модуль базового интерфейса `orchestrator/providers/base.py`."""
    return importlib.import_module(BASE_MODULE)


def registry_entry() -> tuple:
    """(имя атрибута, сам словарь) реестра провайдеров в
    `orchestrator/providers/__init__.py` — первый по алфавиту словарь
    уровня модуля, в котором есть ключ `claude`."""
    module = package()
    found = [(name, value) for name, value in sorted(vars(module).items())
             if isinstance(value, dict) and CLAUDE in value]
    if not found:
        raise AssertionError(
            f"в {PACKAGE}.__init__ нет словаря-реестра с ключом "
            f"'{CLAUDE}'; словари уровня модуля: "
            f"{sorted(n for n, v in vars(module).items() if isinstance(v, dict))}")
    return found[0]


def registry() -> dict:
    """Словарь-реестр провайдеров."""
    return registry_entry()[1]


def entry(name: str = CLAUDE):
    """Значение реестра по имени провайдера."""
    return registry()[name]


def implementation_module(value) -> str:
    """Имя модуля, в котором объявлена реализация из реестра."""
    if isinstance(value, types.ModuleType):
        return value.__name__
    if isinstance(value, type):
        return value.__module__
    own = getattr(value, "__module__", None)
    return own if isinstance(own, str) else type(value).__module__


def instance(value):
    """Объект с методами интерфейса: класс инстанцируется, фабрика
    зовётся, готовый объект или модуль отдаётся как есть."""
    if isinstance(value, types.ModuleType):
        return value
    if isinstance(value, type):
        try:
            return value()
        except TypeError:
            return value
    if callable(value) and not hasattr(value, "command"):
        return value()
    return value


def provider(name: str = CLAUDE):
    """Провайдер по имени — объект, у которого зовутся методы интерфейса."""
    return instance(entry(name))


def patch_target(name: str = CLAUDE):
    """Объект, подмена метода на котором видна ВСЕМУ коду пульта: модуль,
    класс провайдера либо класс зарегистрированного экземпляра."""
    value = entry(name)
    if isinstance(value, (types.ModuleType, type)):
        return value
    obj = instance(value)
    if isinstance(obj, (types.ModuleType, type)):
        return obj
    return type(obj)


def missing_interface_methods(obj) -> list:
    """Методы интерфейса, отсутствующие у объекта (или не вызываемые)."""
    return [name for name in sorted(INTERFACE_METHODS)
            if not callable(getattr(obj, name, None))]


def _first_key(mapping: dict, keys: tuple):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _first_attr(value, names: tuple):
    for name in names:
        found = getattr(value, name, None)
        if found is not None:
            return found
    return None


def version_tuple(value):
    """Минимальная версия кортежем чисел из любой разумной формы:
    кортеж/список чисел, строка `1.0.0`, объект с полем `minimum`."""
    if value is None:
        return None
    if isinstance(value, (tuple, list)) and value and all(
            isinstance(part, int) for part in value):
        return tuple(value)
    if isinstance(value, str):
        parts = value.split(".")
        if parts and all(part.isdigit() for part in parts):
            return tuple(int(part) for part in parts)
        return None
    nested = _first_attr(value, ("minimum", "min_version", "version"))
    return version_tuple(nested) if nested is not None else None


def cli_tool_parts(value) -> tuple:
    """(имя инструмента, минимальная версия кортежем) из значения
    `cli_tool()`: пара, словарь, namedtuple манифеста или объект с
    полями."""
    if (hasattr(value, "minimum") and hasattr(value, "command")
            and not hasattr(value, "name")):
        return None, version_tuple(value.minimum)
    if isinstance(value, dict):
        name = _first_key(value, ("name", "tool", "cli", "tool_name"))
        minimum = _first_key(value, ("minimum", "min_version", "version",
                                     "requirement"))
        return name, version_tuple(minimum)
    if isinstance(value, str):
        return value, None
    if isinstance(value, (tuple, list)) and len(value) == 2:
        first, second = value
        if isinstance(first, str) and not isinstance(second, str):
            return first, version_tuple(second)
        if isinstance(second, str) and not isinstance(first, str):
            return second, version_tuple(first)
        return str(first), version_tuple(second)
    name = _first_attr(value, ("name", "tool", "tool_name"))
    minimum = _first_attr(value, ("minimum", "min_version", "requirement"))
    return name, version_tuple(minimum)


def _looks_like_path(value) -> bool:
    return isinstance(value, Path) or (isinstance(value, str) and "/" in value)


def home_reference_parts(value) -> tuple:
    """(путь референса дома роли, имя развёрнутого каталога) из значения
    `home_reference()`: пара, словарь или объект с полями."""
    if isinstance(value, dict):
        reference = _first_key(value, ("reference", "path", "source",
                                       "directory", "dir", "ref"))
        name = _first_key(value, ("name", "deployed", "deployed_name",
                                  "dest", "dest_name", "target"))
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        first, second = value
        if _looks_like_path(first) and not _looks_like_path(second):
            reference, name = first, second
        elif _looks_like_path(second) and not _looks_like_path(first):
            reference, name = second, first
        else:
            reference, name = first, second
    else:
        reference = _first_attr(value, ("reference", "path", "source",
                                        "directory", "dir"))
        name = _first_attr(value, ("name", "deployed", "deployed_name",
                                   "dest", "dest_name", "target"))
    return (Path(reference) if reference is not None else None,
            str(name) if name is not None else None)
