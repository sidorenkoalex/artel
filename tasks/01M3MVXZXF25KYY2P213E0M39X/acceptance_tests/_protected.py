"""Общий код планки задачи 01M3MVXZXF25KYY2P213E0M39X (защищённые пути —
настройки сбора тестов). Не тестовый модуль: префикс `_` обязателен,
иначе checkpoint отбросит файл как посторонний (skills/test-authoring.md).

Держит три вещи, нужные больше чем одному `test_*.py`:

1. Перечни путей критериев приёмки — прежние 12 записей, пять новых,
   похожие незащищённые пути. В одном месте, потому что AC-2/AC-3/AC-6/
   AC-10 говорят об одних и тех же наборах и обязаны спрашивать их
   одинаково.

2. `comparison_helpers()` — резолвер помощника сравнения пути с перечнем
   из `orchestrator/config.py`. SPEC называет МЕСТО помощника
   (требование 4, AC-2/AC-3), но не его имя: угадывать имя значило бы
   писать тест на фантазию сверх SPEC, поэтому планка находит помощника
   по контракту «функция модуля `orchestrator/config.py`, зовущаяся с
   одним строковым путём и отвечающая вердиктом AC-10 на прежних
   записях». Сегодня в `orchestrator/config.py` нет ни одной функции
   вовсе (только константы и `from pathlib import Path`), поэтому
   контракт не может опознать постороннюю функцию.

3. `place_verdicts()` — вердикт «путь защищён» у КАЖДОГО из шести мест
   сверки требования 5, под именем места. AC-10 спрашивает все шесть, и
   один адрес вердикта избавляет его файл от шести разных форм вызова.
"""
import inspect
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

TASK_ID = "01M3MVXZXF25KYY2P213E0M39X"

#: Прежние 12 записей `config.PROTECTED_PATHS` в прежнем порядке —
#: снимок состояния ДО задачи (`orchestrator/config.py:652` головы
#: e29e5832). Литерал здесь законен и неизбежен: AC-1 говорит буквально
#: «прежние 12 записей — на прежних местах в прежнем порядке», и сверить
#: это не с чем, кроме снимка.
LEGACY_ENTRIES = ("gates.yaml", "roles.yaml", ".github/",
                  "templates/", "skills/", "docs/invariants.md",
                  "tests/test_invariants.py", "docs/adr/", "CLAUDE.md",
                  "AGENTS.md", "targets.yaml", "models.yaml")

#: Запись-маска требования 1-2 и четыре корневых литерала.
MASK_ENTRY = "**/conftest.py"
NEW_ENTRIES = (MASK_ENTRY, "pyproject.toml", "pytest.ini", "setup.cfg",
               "tox.ini")

#: Пути, которые новые записи обязаны покрыть (AC-2; тот же набор
#: спрашивает AC-6 у джоба CI).
PROTECTED_NEW_PATHS = ("conftest.py", "tests/conftest.py",
                       "tests/sub/conftest.py", "pyproject.toml",
                       "pytest.ini", "setup.cfg", "tox.ini")

#: Пути, похожие на новые записи и защищёнными НЕ являющиеся (AC-3).
#: `tests/pytest.ini` — вложенный литерал требования 3: «в любом
#: каталоге» действует только для `conftest.py`.
UNPROTECTED_LOOKALIKE_PATHS = ("tests/test_conftest_role_guard.py",
                               "docs/pyproject.md", "conftest.py.bak",
                               "tests/pytest.ini")

#: Пути, которые AC-6 называет ненарушением джоба CI — подмножество
#: набора выше (критерий называет ровно эти два).
CI_NON_VIOLATION_PATHS = ("tests/test_conftest_role_guard.py",
                          "docs/pyproject.md")

#: Вердикт на прежних 12 записях (AC-10): защищён / не защищён.
LEGACY_PROTECTED_SAMPLES = ("gates.yaml", ".github/workflows/ci.yml",
                            "docs/adr/0001-foo.md", "templates/SPEC.md")
LEGACY_UNPROTECTED_SAMPLES = ("orchestrator/store.py", "tests/test_store.py")

#: Пути AC-4/AC-5 — на них сверяются гейт зон и гейт диффа на мерже.
GATE_PATHS = ("conftest.py", "pyproject.toml", "tests/sub/conftest.py")

HELPER_CONTRACT = (
    "помощник сравнения пути с перечнем защищённых путей (SPEC требование "
    "4) — функция УРОВНЯ МОДУЛЯ `orchestrator/config.py`, которую планка "
    "зовёт одним позиционным строковым путём и вердикт которой на прежних "
    f"записях совпадает с AC-10: истинна на {LEGACY_PROTECTED_SAMPLES[0]} и "
    f"{LEGACY_PROTECTED_SAMPLES[2]}, ложна на {LEGACY_UNPROTECTED_SAMPLES[0]} "
    f"и {LEGACY_UNPROTECTED_SAMPLES[1]}. Ни одной такой функции в модуле нет "
    "— имя помощника планка не навязывает, форму вызова навязывает")

#: Опорный вердикт резолвера: два защищённых и два незащищённых пути
#: прежних записей (AC-10). Ровно тот контракт, который описан выше.
_BASELINE = ((LEGACY_PROTECTED_SAMPLES[0], True),
             (LEGACY_PROTECTED_SAMPLES[2], True),
             (LEGACY_UNPROTECTED_SAMPLES[0], False),
             (LEGACY_UNPROTECTED_SAMPLES[1], False))


def comparison_helpers() -> list:
    """[(имя, функция)] помощников сравнения из `orchestrator/config.py`,
    опознанных по контракту `HELPER_CONTRACT` — пустой список означает,
    что помощника в модуле нет (либо он зовётся иначе, чем одним
    строковым путём).

    Кандидат — функция, ОПРЕДЕЛЁННАЯ в `orchestrator/config.py`
    (`__module__`), а не привезённая импортом: сам модуль по требованию 4
    самодостаточен, и чужую функцию контракт бы не опознал.

    Вердикт кандидата берётся по истинности (`bool(...)`), не `is True`:
    критерий говорит «признаёт защищённым», а не «возвращает ровно
    `True`» — помощник, отдающий совпавшую запись перечня вместо флага,
    критерию отвечает.
    """
    found = []
    for name, obj in vars(config).items():
        if not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != config.__name__:
            continue
        try:
            verdicts = [bool(obj(path)) for path, _ in _BASELINE]
        except Exception:  # noqa: BLE001 — кандидат не подошёл, не сбой планки
            continue
        if verdicts == [expected for _, expected in _BASELINE]:
            found.append((name, obj))
    return found


def _touched_via_github_adapter(paths: list) -> list:
    """Вердикт места №6 требования 5 (`github_adapter.
    _touched_protected_paths`) без настоящего git: единственный внешний
    вход этой функции — вывод `git diff --name-only`, и подменяется
    именно он (`gitcmd.git`), а не список защищённых путей."""
    from orchestrator import github_adapter, gitcmd

    completed = subprocess.CompletedProcess(
        args=("git", "diff", "--name-only"), returncode=0,
        stdout="".join(f"{p}\n" for p in paths), stderr="")
    with mock.patch.object(gitcmd, "git", return_value=completed):
        return github_adapter._touched_protected_paths("task/plank-x", "base")


def place_verdicts(path: str) -> dict:
    """{имя места требования 5: «место считает `path` защищённым»} — все
    ШЕСТЬ мест сверки пути с перечнем, каждое своей публичной формой
    вызова (имена и сигнатуры сохраняются, требование 5).

    Места, отдающие СПИСОК путей, сводятся к вердикту сравнением с
    `[path]`: спрашивается один путь, и список из него — это «защищён»,
    пустой — «не защищён»."""
    from orchestrator import fsm_merge_gate
    from orchestrator.advance_gates import zones
    from scripts import ci_protected_paths, guard

    protected = list(config.PROTECTED_PATHS)
    return {
        "fsm_merge_gate._touches_protected_path":
            bool(fsm_merge_gate._touches_protected_path(path)),
        "advance_gates.zones._protected_paths_touched":
            zones._protected_paths_touched([path]) == [path],
        "ci_protected_paths.is_violation":
            bool(ci_protected_paths.is_violation(path, protected)),
        "guard._appendix_path_is_protected":
            bool(guard._appendix_path_is_protected(path)),
        "guard.protected_zones":
            guard.protected_zones([path]) == [path],
        "github_adapter._touched_protected_paths":
            _touched_via_github_adapter([path]) == [path],
    }
