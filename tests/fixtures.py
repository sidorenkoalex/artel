"""Фикстуры-песочницы в стиле pytest над классами `tests/sandbox.py` (ADR-0027, часть А1).

Фикстура — переходник: создаёт экземпляр ровно своего класса песочницы,
зовёт его `setUp()` и отдаёт экземпляр; тест берёт его атрибуты и методы
так же, как наследник `unittest.TestCase` берёт `self`.

Уборку фикстура исполняет сама, а не через `doCleanups()`: вне раннера
unittest тот проглатывает ошибку упавшего действия и возвращает только
`False` — текст ошибки из него не получить (SPEC 01M5N9V4S984GRRXSMBK5JX7V1,
решение Оператора на гейте SPEC 24.10.2026).

`tests.sandbox` импортируется внутри фикстур, не на уровне модуля: его
импорт меняет состояние процесса (`shutil.which`, `config.ROLES`,
`config.TWO_SIDED_OBSERVATION`), а этот модуль подключает корневой
`conftest.py` всем прогонам, в том числе не берущим песочницу.
"""
import pytest


def _run_cleanups(obj) -> list:
    """Исполняет действия уборки `obj` в обратном порядке регистрации.

    Упавшее действие не останавливает остальные; возвращает исключения
    упавших действий. Действие, зарегистрированное во время уборки,
    исполняется тем же циклом — как у `doCleanups()`.
    """
    errors = []
    while obj._cleanups:
        function, args, kwargs = obj._cleanups.pop()
        try:
            function(*args, **kwargs)
        except Exception as exc:
            errors.append(exc)
    return errors


def _cleanup_message(cls, errors: list) -> str:
    return (f"уборка песочницы {cls.__name__} упала: "
            + "; ".join(repr(exc) for exc in errors))


def _sandbox(cls):
    obj = cls()
    try:
        obj.setUp()
    except BaseException as exc:
        errors = _run_cleanups(obj)
        if errors:
            exc.add_note(_cleanup_message(cls, errors))
        raise
    yield obj
    errors = _run_cleanups(obj)
    if errors:
        raise RuntimeError(_cleanup_message(cls, errors))


@pytest.fixture
def tmp_dir():
    """Экземпляр `TmpDirTest` после `setUp()`: временный каталог `tdir`."""
    from tests.sandbox import TmpDirTest
    yield from _sandbox(TmpDirTest)


@pytest.fixture
def tmp_root():
    """Экземпляр `TmpRootTest` после `setUp()`: пути `config` под `root`."""
    from tests.sandbox import TmpRootTest
    yield from _sandbox(TmpRootTest)


@pytest.fixture
def initialized_tmp_root():
    """Экземпляр `InitializedTmpRootTest` после `setUp()`: `root` после `cmd_init`."""
    from tests.sandbox import InitializedTmpRootTest
    yield from _sandbox(InitializedTmpRootTest)


@pytest.fixture
def real_git():
    """Экземпляр `RealGitSandbox` после `setUp()`: настоящий git-репозиторий в `root`."""
    from tests.sandbox import RealGitSandbox
    yield from _sandbox(RealGitSandbox)


@pytest.fixture
def origin_real_git():
    """Экземпляр `OriginRealGitSandbox` после `setUp()`: bare-origin по явному `add_origin()`."""
    from tests.sandbox import OriginRealGitSandbox
    yield from _sandbox(OriginRealGitSandbox)


@pytest.fixture
def light_transition():
    """Экземпляр `LightTransitionSandbox` после `setUp()`: лёгкая песочница переходов FSM."""
    from tests.sandbox import LightTransitionSandbox
    yield from _sandbox(LightTransitionSandbox)
