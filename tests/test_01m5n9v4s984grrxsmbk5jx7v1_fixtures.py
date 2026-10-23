"""Фикстуры-песочницы `tests.fixtures` в стиле pytest (ADR-0027, часть А1).

Группа: долгоживущий
Красен до реализации: модуля tests/fixtures.py ещё нет — импорт фикстур на уровне модуля падает ImportError, весь файл не собирается.

Фикстуры импортированы из `tests.fixtures` явно — файл не полагается на
подключение из корневого `conftest.py`. Свойства уборки (AC-2…AC-5)
проверяются ручным прогоном функции фикстуры: `<фикстура>.__wrapped__()` —
генератор, первый `next` отдаёт экземпляр песочницы, второй исполняет
уборку; так видно и состояние после завершения фикстуры, и исключение
уборки (`pytest.raises`). Видимость фикстуры раннером pytest (AC-1, AC-8)
— через `request.getfixturevalue`, видимость в чужом дереве с подключением
`pytest_plugins` (AC-7) и чистота импорта (AC-6) — подпроцессом.
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import config
from tests import fixtures
from tests.fixtures import (initialized_tmp_root, light_transition,  # noqa: F401
                            origin_real_git, real_git, tmp_dir, tmp_root)

CODE_ROOT = Path(__file__).resolve().parents[1]

# Фикстура -> класс `tests/sandbox.py`, который она обязана отдавать (AC-1).
FIXTURE_CLASSES = {
    "tmp_dir": "TmpDirTest",
    "tmp_root": "TmpRootTest",
    "initialized_tmp_root": "InitializedTmpRootTest",
    "real_git": "RealGitSandbox",
    "origin_real_git": "OriginRealGitSandbox",
    "light_transition": "LightTransitionSandbox",
}
ROOT_FIXTURES = [name for name in FIXTURE_CLASSES if name != "tmp_dir"]

SEED = random.randrange(2 ** 32)
print(f"зерно: {SEED}")
RNG = random.Random(SEED)


def token(prefix: str) -> str:
    """Метка исключения, уникальная на запуск — её `repr` ищется в тексте."""
    return f"{prefix}-{RNG.randrange(10 ** 9)}-зерно-{SEED}"


def sandbox_class(fixture_name: str):
    from tests import sandbox
    return getattr(sandbox, FIXTURE_CLASSES[fixture_name])


def start(fixture_name: str):
    """(генератор фикстуры, экземпляр) — фикстура запущена до `yield`."""
    gen = getattr(fixtures, fixture_name).__wrapped__()
    return gen, next(gen)


def finish(gen) -> None:
    """Завершение фикстуры: исполняется её уборка; второго `yield` нет."""
    try:
        next(gen)
    except StopIteration:
        return
    raise AssertionError(f"фикстура отдала второе значение (зерно {SEED})")


def sandbox_root(obj) -> Path:
    return Path(obj.tdir if isinstance(obj, sandbox_class("tmp_dir"))
                else obj.root).resolve()


def is_temporary(path: Path) -> bool:
    return path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())


def config_snapshot() -> dict:
    from tests.sandbox import ALL_CONFIG_ATTRS
    return {attr: getattr(config, attr) for attr in ALL_CONFIG_ATTRS}


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CLASSES))
def test_ac1_fixture_yields_exact_sandbox_class(request, fixture_name):
    """Тест берёт фикстуру через раннер pytest и получает экземпляр ровно её класса после `setUp`.

    Экземпляр — не подкласс (`type(obj) is <класс>`), и `setUp` уже
    исполнен: у `TmpDirTest` есть `tdir`, у прочих — `root`.

    Ловит мутацию: фикстура `initialized_tmp_root` отдаёт `TmpRootTest`
    (перепутан класс в таблице переходника) либо `real_git` — подкласс
    `GitignoreCommittedRealGitSandbox`; либо `setUp()` не вызван — нет
    атрибута `root`/`tdir`, тест краснеет.
    """
    obj = request.getfixturevalue(fixture_name)
    cls = sandbox_class(fixture_name)
    assert type(obj) is cls, (
        f"{fixture_name}: {type(obj).__name__}, ожидался {cls.__name__}")
    attr = "tdir" if fixture_name == "tmp_dir" else "root"
    assert Path(getattr(obj, attr)).is_dir(), (
        f"{fixture_name}: нет каталога {attr} — setUp() не исполнен")


@pytest.mark.parametrize("fixture_name", ["tmp_dir"])
@pytest.mark.parametrize("nested", [False, True])
def test_ac2_tmp_dir_is_temporary_and_removed(fixture_name, nested):
    """Каталог `tdir` экземпляра временный во время теста и удалён после завершения фикстуры.

    Вариант `nested` кладёт в каталог вложенный файл — уборка обязана
    снять и непустой каталог.

    Ловит мутацию: фикстура не исполняет зарегистрированные действия
    уборки (нет вызова `tmp.cleanup`) — каталог `tdir` остаётся на диске
    после `finish`, тест краснеет.
    """
    gen, obj = start(fixture_name)
    tdir = Path(obj.tdir)
    assert tdir.is_dir() and is_temporary(tdir), f"{tdir} не временный"
    if nested:
        (tdir / "a" / "b").mkdir(parents=True)
        (tdir / "a" / "b" / token("файл")).write_text("x", encoding="utf-8")
    finish(gen)
    assert not tdir.exists(), f"{tdir} не удалён после фикстуры"


@pytest.mark.parametrize("fixture_name", ROOT_FIXTURES)
def test_ac3_config_patched_then_restored_and_root_removed(fixture_name):
    """Пути `config` подменены на временный корень во время теста и возвращены после фикстуры.

    Во время: каждое имя `ALL_CONFIG_ATTRS` указывает внутрь `root`
    экземпляра, корень — временный каталог. После: значения `config` те
    же, что до фикстуры, корень удалён.

    Ловит мутацию: фикстура зовёт только первое действие уборки (или
    останавливается на первом) — патчи `config` остаются, `config.DB`
    после фикстуры указывает в удалённый временный корень, тест краснеет.
    """
    before = config_snapshot()
    gen, obj = start(fixture_name)
    root = sandbox_root(obj)
    try:
        assert is_temporary(root), f"{fixture_name}: корень {root} не временный"
        for attr, value in config_snapshot().items():
            assert Path(value).resolve().is_relative_to(root), (
                f"{fixture_name}: config.{attr}={value} вне корня {root}")
    finally:
        finish(gen)
    assert config_snapshot() == before, f"{fixture_name}: подмены config не сняты"
    assert not root.exists(), f"{fixture_name}: корень {root} не удалён"


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CLASSES))
def test_ac4_failed_cleanup_raises_runtime_error(fixture_name):
    """Упавшее действие уборки поднимает `RuntimeError` с классом песочницы и `repr` исключения.

    Тест регистрирует на экземпляре метку, падающее действие и вторую
    метку; завершение фикстуры обязано поднять `RuntimeError`, а обе метки
    и собственная уборка песочницы (удаление корня) — отработать.

    Ловит мутацию: сбор ошибок уборки и подъём `RuntimeError` убраны
    (уборка через `doCleanups()`, чей `False` игнорируется) — фикстура
    завершается тихим успехом, `pytest.raises` краснеет.
    """
    gen, obj = start(fixture_name)
    root = sandbox_root(obj)
    marks: list = []
    failure = ValueError(token("уборка"))

    def failing():
        raise failure

    obj.addCleanup(marks.append, "первая")
    obj.addCleanup(failing)
    obj.addCleanup(marks.append, "вторая")
    cls_name = FIXTURE_CLASSES[fixture_name]
    with pytest.raises(RuntimeError, match=re.escape(cls_name)) as caught:
        finish(gen)
    assert repr(failure) in str(caught.value), (
        f"в сообщении нет {failure!r}: {caught.value} (зерно {SEED})")
    assert sorted(marks) == ["вторая", "первая"], f"отработали не все: {marks}"
    assert not root.exists(), f"{fixture_name}: уборка песочницы не отработала"


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CLASSES))
def test_ac4_cleanup_runs_in_reverse_registration_order(fixture_name):
    """Два действия уборки, зарегистрированные тестом, исполняются в порядке, обратном регистрации.

    Ловит мутацию: прямой порядок (действия снимаются и зовутся в порядке
    регистрации, без `reversed`) — метки ложатся как «первая», «вторая»,
    тест краснеет.
    """
    gen, obj = start(fixture_name)
    marks: list = []
    first, second = token("первая"), token("вторая")
    obj.addCleanup(marks.append, first)
    obj.addCleanup(marks.append, second)
    finish(gen)
    assert marks == [second, first], f"порядок уборки {marks} (зерно {SEED})"


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CLASSES))
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_ac5_setup_failure_cleans_up_and_reraises(fixture_name, cleanup_fails):
    """`setUp()` падает внутри фикстуры: уборка отработала, наружу — исходное исключение.

    Подменённый `setUp` исполняет настоящий, регистрирует метку (и, в
    варианте `cleanup_fails`, падающее действие уборки) и падает
    `ValueError`. Наружу — тот же класс и текст; корень песочницы удалён,
    `config` прежний, метка стоит. При упавшем действии уборки у исходного
    исключения есть заметка с классом песочницы и `repr` исключения
    уборки.

    Ловит мутацию: при сбое `setUp` фикстура пробрасывает исключение, не
    исполнив уборку (нет `try/except` вокруг `setUp`) — метки нет, корень и
    патчи `config` остаются; либо ошибки уборки не добавлены `add_note` —
    у исключения нет `__notes__`, тест краснеет.
    """
    cls = sandbox_class(fixture_name)
    original_setup = cls.setUp
    marks: list = []
    setup_error = ValueError(token("setUp"))
    cleanup_error = KeyError(token("уборка"))
    roots: list = []

    def failing_cleanup():
        raise cleanup_error

    def broken_setup(self):
        original_setup(self)
        roots.append(sandbox_root(self))
        self.addCleanup(marks.append, "метка")
        if cleanup_fails:
            self.addCleanup(failing_cleanup)
        raise setup_error

    before = config_snapshot()
    with mock.patch.object(cls, "setUp", broken_setup):
        with pytest.raises(ValueError) as caught:
            start(fixture_name)
    exc = caught.value
    assert type(exc) is ValueError and str(exc) == str(setup_error), (
        f"наружу {exc!r}, ожидалось {setup_error!r}")
    assert marks == ["метка"], f"уборка после сбоя setUp не отработала: {marks}"
    assert roots and not roots[0].exists(), f"корень {roots} не удалён"
    assert config_snapshot() == before, "подмены config не сняты после сбоя setUp"
    if cleanup_fails:
        notes = "\n".join(getattr(exc, "__notes__", []))
        assert cls.__name__ in notes and repr(cleanup_error) in notes, (
            f"заметка {notes!r} не называет {cls.__name__} и "
            f"{cleanup_error!r} (зерно {SEED})")


IMPORT_PROBE = """
import json, shutil, sys
from orchestrator import config
watched = lambda: {"TWO_SIDED_OBSERVATION": config.TWO_SIDED_OBSERVATION,
                   "ROLES": config.ROLES, "which": shutil.which}
preloaded = "tests.sandbox" in sys.modules
before = watched()
__import__(sys.argv[1])
after = watched()
print(json.dumps({"preloaded": preloaded,
                  "changed": sorted(k for k in before if before[k] is not after[k]
                                    and before[k] != after[k])}))
"""


@pytest.mark.parametrize("module, expect_changed", [
    ("tests.fixtures", []),
    # Контроль пробы: импорт самой песочницы меняет все три значения —
    # без него проба, не видящая перемен, прошла бы и с поломкой.
    ("tests.sandbox", ["ROLES", "TWO_SIDED_OBSERVATION", "which"]),
])
def test_ac6_import_does_not_touch_process_state(module, expect_changed):
    """Импорт `tests.fixtures` в свежем процессе не меняет `config.TWO_SIDED_OBSERVATION`, `config.ROLES` и `shutil.which`.

    Подпроцесс импортирует модуль, где `tests.sandbox` ещё не импортирован,
    и сравнивает три значения до и после; контрольный вариант —
    импорт `tests.sandbox`, меняющий все три.

    Ловит мутацию: импорт `tests.sandbox` на уровне модуля
    `tests/fixtures.py` — после импорта `config.ROLES` уведён на фикстуру,
    `TWO_SIDED_OBSERVATION` стал `False`, `shutil.which` подменён, тест
    краснеет.
    """
    proc = subprocess.run([sys.executable, "-c", IMPORT_PROBE, module],
                          cwd=CODE_ROOT, capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["preloaded"] is False, "tests.sandbox импортирован заранее"
    assert result["changed"] == expect_changed, (
        f"импорт {module} изменил {result['changed']}")


INNER_TEST = "\n".join(
    f"def test_{name}({name}):\n"
    f"    assert type({name}).__name__ == {cls!r}\n"
    for name, cls in FIXTURE_CLASSES.items())


@pytest.mark.parametrize("with_plugins", [True, False])
def test_ac7_fixtures_visible_to_plank_via_conftest(tmp_path, with_plugins):
    """Во временном проекте с `conftest.py`, несущим `pytest_plugins`, фикстуры видны тесту каталога приёмочных тестов задачи.

    Временный проект: `conftest.py` со строкой приложения и тест под
    `<каталог задач>/<id>/acceptance_tests/`, берущий все шесть фикстур;
    pytest — подпроцессом с флагами гейта. Контроль: без строки
    `pytest_plugins` те же фикстуры не найдены.

    Ловит мутацию: фикстура в `tests/fixtures.py` объявлена под другим
    именем (например `real_git_sandbox`) или без `@pytest.fixture` —
    внутренний прогон падает «fixture 'real_git' not found», тест
    краснеет.
    """
    conftest = 'pytest_plugins = ["tests.fixtures"]\n' if with_plugins else ""
    (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
    plank = Path("tasks") / "01PROBE" / "acceptance_tests"
    (tmp_path / plank).mkdir(parents=True)
    (tmp_path / plank / "test_probe.py").write_text(INNER_TEST, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(CODE_ROOT)] + [p for p in [env.get("PYTHONPATH")] if p])
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(plank / "test_probe.py"),
         "-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    output = proc.stdout + proc.stderr
    if with_plugins:
        assert proc.returncode == 0, output
        assert f"{len(FIXTURE_CLASSES)} passed" in output, output
    else:
        assert proc.returncode != 0, output
        assert "fixture 'tmp_root' not found" in output, output


@pytest.mark.parametrize("fixture_name, call", [
    ("real_git", lambda obj: obj.git("rev-parse", "--abbrev-ref", "HEAD")),
    ("light_transition", lambda obj: obj.state()),
])
def test_ac8_sandbox_methods_work_through_fixture(request, fixture_name, call):
    """Методы класса работают через фикстуру: `git()` у `real_git`, `state()` у `light_transition`.

    `git("rev-parse", "--abbrev-ref", "HEAD")` отвечает веткой репозитория
    песочницы, `state()` — состоянием заведённой песочницей задачи;
    оба — непустая строка без исключения.

    Ловит мутацию: фикстура отдаёт экземпляр уже после уборки (`return`
    вместо `yield` перед уборкой) — корень `real_git` удалён, `git()`
    падает на несуществующем `cwd`; патчи `config` `light_transition` сняты,
    `state()` не находит задачу в боевой БД, тест краснеет.
    """
    obj = request.getfixturevalue(fixture_name)
    result = call(obj)
    assert isinstance(result, str) and result.strip(), (
        f"{fixture_name}: пустой результат {result!r}")
