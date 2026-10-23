"""Выкладка планки в рабочую копию: самодостаточная часть (SPEC
01M5N8ASJ63ZKF3M9ETC7A3P5V, CR-2026-10-22-8, этап 1).

Перенесено из `orchestrator/acceptance.py` без изменения поведения и
текстов отказов; `acceptance` сохраняет прежние имена реэкспортом тех же
объектов. Часть, которая зовёт раннеры и профиль проекта (`_layout_ignore`,
`_layout_check`, `_plank_plan`, `_component_layout`, `_laid_plank`),
остаётся в `acceptance`. Модуль `acceptance` не импортирует.
"""
import contextlib
import fcntl
import os
import shutil
from pathlib import Path
from typing import Iterator, NamedTuple

from . import gitcmd

# ------------------------------------------------ выкладка планки `pytest-own`
#
# Планка внешнего проекта исполняется из каталога внутри `long_lived_dir`
# рабочей копии (SPEC 01M57JYJQC8VAHEWMXFNM7D1GS): только там pytest видит
# корень, конфиг, `pythonpath` и `conftest.py` проекта так же, как у
# долгоживущего теста. `--rootdir`/`-c` фикстур `conftest.py` не дают — они
# применяются лишь к тестам под его каталогом.
PLANK_LAYOUT_DIR = ".artel-plank"
# Один общий шаблон в `info/exclude` клона (файл общий для всех worktree
# проекта — потому без id задачи): чекпоинт коммитит `git add -A`, и
# неотслеживаемый файл выкладки, переживший обрыв, иначе ушёл бы в ветку.
PLANK_LAYOUT_EXCLUDE = f"**/{PLANK_LAYOUT_DIR}/"
LAYOUT_OUTSIDE_NOTE = ("long_lived_dir профиля «{lld}» лежит вне workdir "
                       "«{workdir}» — планка идёт прежним путём из "
                       "tasks/<id>/acceptance_tests, без выкладки")


def _inside(path: str, folder: str) -> bool:
    path, folder = os.path.normpath(path), os.path.normpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def layout_mode(own) -> str:
    """«layout» — планка выкладывается под `long_lived_dir`; «outside» —
    `long_lived_dir` вне `workdir`, прежний путь со строкой о случае; «» —
    не `pytest-own` с `workdir`, прежний путь молча."""
    if own is None or not own.workdir:
        return ""
    return "layout" if _inside(own.long_lived_dir, own.workdir) else "outside"


def layout_root(code_root: Path, own, task_id: str) -> Path:
    return Path(code_root) / own.long_lived_dir / PLANK_LAYOUT_DIR / task_id


def exclude_layout(code_root: Path) -> str:
    """Шаблон выкладки в `info/exclude` клона рабочей копии `code_root`,
    если его там ещё нет; текст отказа — git не ответил или файл не
    записан (выкладку, видимую git, класть нельзя).

    Файл общий для всех worktree клона, и задачи дописывают его
    параллельно: проверка «шаблон уже есть» и дописывание идут под
    `flock` на самом файле, иначе две задачи оставили бы две строки."""
    return exclude_pattern(code_root, PLANK_LAYOUT_EXCLUDE, "выкладки планки")


def exclude_pattern(code_root: Path, pattern: str, what: str) -> str:
    """Шаблон `pattern` в `info/exclude` клона рабочей копии `code_root`
    (`exclude_layout`); текст отказа «отказ <what>: …» или пусто."""
    res = gitcmd.in_repo(Path(code_root), "rev-parse", "--git-path",
                         "info/exclude")
    if res is None or res.returncode != 0 or not res.stdout.strip():
        detail = (res.stderr.strip() if res is not None else "") or "нет ответа"
        return (f"отказ {what}: git не назвал info/exclude рабочей "
                f"копии {code_root} ({detail}) — pytest не запускался")
    path = Path(res.stdout.strip())
    if not path.is_absolute():
        path = Path(code_root) / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.seek(0)
                text = fh.read()
                if pattern not in text.splitlines():
                    fh.write(("" if not text or text.endswith("\n") else "\n")
                             + pattern + "\n")
                    fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except (OSError, UnicodeDecodeError) as exc:
        return (f"отказ {what}: {path} не записан ({exc}) — pytest "
                f"не запускался")
    return ""


def drop_layout(root: Path) -> None:
    """Каталог выкладки задачи `root` вместе с кешем байткода; пустой
    `.artel-plank/` над ним — тоже."""
    shutil.rmtree(root, ignore_errors=True)
    try:
        root.parent.rmdir()
    except OSError:
        pass


@contextlib.contextmanager
def plank_layout(task_id: str, tests_dir: Path, code_root: Path,
                 own) -> Iterator[tuple[Path | None, str, str]]:
    """(каталог планки в выкладке или `None`, строка о случае, текст отказа)
    на время блока. Выкладка — копия `tests_dir` (как он лежит на диске:
    штатная выкладка или правка Оператора с помощником) в
    `<code_root>/<long_lived_dir>/.artel-plank/<id>/acceptance_tests`;
    исключение из git — до записи файлов, уборка — в `finally` на любом
    исходе прогона."""
    mode = layout_mode(own)
    if mode != "layout":
        note = (LAYOUT_OUTSIDE_NOTE.format(lld=own.long_lived_dir,
                                           workdir=own.workdir)
                if mode == "outside" else "")
        yield None, note, ""
        return
    refusal = exclude_layout(code_root)
    if refusal:
        yield None, "", refusal
        return
    root = layout_root(code_root, own, task_id)
    try:
        shutil.rmtree(root, ignore_errors=True)
        layout = root / "acceptance_tests"
        shutil.copytree(tests_dir, layout,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        yield layout, "", ""
    finally:
        drop_layout(root)


# ------------------------------------------------ выкладка по `plank_layout`
#
# Компонент записи `components:` с `report` и `plank_layout` (SPEC
# 01M59Z0FW1699SJQ2FA5Y76CZ3; ADR-0026 п. 5): на время прогона файлы планки
# его компонента лежат прямо в `<plank_layout>` рабочей копии, без
# подкаталога `acceptance_tests`. Родитель `<id>` — скрытый каталог без
# отслеживаемых файлов: шаблон `/<родитель>/` в `info/exclude` прячет только
# выкладку, не код.
PLANK_ABSENT_NOTE = "acceptance_tests/ нет — приёмочные тесты не заведены"
NO_PLANK_LAYOUT = ("у компонента {name} нет plank_layout — выкладка планки "
                   "не определена")
LAYOUT_NOT_NORMAL = "plank_layout должен быть нормализованным путём без «.» и «..»"
LAYOUT_ID_NOT_LAST = "<id> должен быть последним сегментом plank_layout"
LAYOUT_OUTSIDE_WORKDIR = "plank_layout вне рабочего каталога компонента {name}"
LAYOUT_PARENT_NOT_HIDDEN = ("родитель <id> в plank_layout должен быть скрытым "
                            "каталогом (имя с точки)")
LAYOUT_PARENT_TRACKED = ("в каталоге {parent} есть отслеживаемые git файлы — "
                         "выкладка спрятала бы их")
_LAYOUT_ID = "<id>"


def uses_plank_layout(profile) -> bool:
    """`plank_layout` читается только у компонента записи `components:` с
    `report` (требования 5, 7); у прочих профилей поле не действует."""
    return bool(getattr(profile, "from_components", False)
                and getattr(profile, "report", "")
                and getattr(profile, "plank_layout", ""))


def _layout_parent(layout: str) -> str:
    """Родитель `<id>` в `plank_layout` нормализованной формы с `<id>`
    последним сегментом; пусто — форма не та (`acceptance._layout_check`)."""
    parts = layout.split("/")
    if any(p in ("", ".", "..") for p in parts) or parts[-1] != _LAYOUT_ID:
        return ""
    return "/".join(parts[:-1])


class PlankPlan(NamedTuple):
    """Решение по планке места прогона до запуска (требования 1, 5, 6):
    `refusal` — отказ подготовки; `absent` — файлов компонента нет, та же
    «планка не заведена»; `files` — файлы компонента для выкладки по
    `plank_layout` (`tests` — из них тестовые); иначе — прежний путь."""
    refusal: str = ""
    absent: bool = False
    files: tuple = ()
    tests: tuple = ()
    profile: object = None


class Laid(NamedTuple):
    """Выкладка на время блока: `targets` — цели планки вместо каталога
    планки (`None` — прежние), `root` — каталог, соответствующий каталогу
    планки; `note` — строка о случае; `refusal` — отказ подготовки."""
    targets: list | None = None
    root: Path | None = None
    note: str = ""
    refusal: str = ""


def drop_component_layout(root: Path) -> None:
    """Каталог `<id>` выкладки; родитель — только если он опустел."""
    shutil.rmtree(root, ignore_errors=True)
    with contextlib.suppress(OSError):
        root.parent.rmdir()
