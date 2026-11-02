"""Приложение PLAN к защищённому `tests/test_invariants.py`: `verify-ok` и `verify-fail` в обходе команд `FsmTest.commands` на песочнице с `verify: [human:stand]`.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет в ссылке документов (`artifact_text("PLAN.md")` — `None`), приложения к `tests/test_invariants.py` разбирать не из чего.

Источник приложения — PLAN.md ссылки документов задачи (помощник пульта
`_pult.artifact_text`), разбор — тем же `scripts.guard.plan_appendices`,
которым его читают гейт применимости и мерж. Применимость — `apply_check`
помощника к дереву HEAD кодовой ветки. Зелёный обход проверяется
исполнением: приложение накладывается во временной отвязанной рабочей
копии HEAD, и в ней прогоняется `tests/test_invariants.py` целиком.

Провалидировано вручную (стаб удалён, не закоммичен): ход «рабочая копия
HEAD — `git apply` — прогон `tests/test_invariants.py`» на пробном диффе
даёт код 0; без PLAN.md файл красен по причине маркера.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from scripts import guard  # noqa: E402

INVARIANTS = "tests/test_invariants.py"
SWEEP_TIMEOUT_SEC = 110


def invariants_diffs() -> list:
    """Тексты блоков приложений PLAN.md, затрагивающих `tests/test_invariants.py`."""
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md нет в ссылке документов задачи"
    appendices, errors = guard.plan_appendices(plan)
    diffs = [a.diff for a in appendices if INVARIANTS in a.paths]
    assert diffs, (f"в PLAN.md нет приложения к {INVARIANTS}; ошибки разбора: "
                   f"{errors}")
    return diffs


def added_lines(diffs: list) -> list:
    return [line for diff in diffs for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")]


def test_ac20_appendix_adds_verify_commands_and_applies():
    """Приложение PLAN к `tests/test_invariants.py` добавляет команды `verify-ok` и `verify-fail` в обход и профиль `verify: [human:stand]` песочницы, и `git apply --check` проходит на чистом дереве.

    Сценарий: PLAN.md из ссылки документов; разбор приложений guard —
    есть блок с путём `tests/test_invariants.py`. Среди добавленных строк
    его диффа есть строки с `verify-ok`, с `verify-fail` и с
    `human:stand`. `apply_check` каждого такого блока к дереву HEAD — пусто
    (git согласен).

    Ловит мутацию: приложение не вносит одну из команд (только
    `verify-ok`); песочница обхода без профиля `verify` (команды отказали
    бы, не сработав); хедер хунка не совпадает с файлом — `git apply
    --check` отвечает ошибкой.
    """
    diffs = invariants_diffs()
    added = added_lines(diffs)
    for word in ("verify-ok", "verify-fail", "human:stand"):
        assert any(word in line for line in added), (
            f"добавленные строки приложения не несут «{word}»:\n"
            + "\n".join(added))
    for diff in diffs:
        answer = apply_check(diff)
        assert answer == "", f"git apply --check отказал:\n{answer}"


def test_ac20_sweep_with_appendix_is_green():
    """Обход команд с приложением зелёный: в рабочей копии HEAD с наложенным приложением `tests/test_invariants.py` проходит целиком.

    Сценарий: временная отвязанная рабочая копия HEAD кодовой ветки
    (`git worktree add --detach`), в ней `git apply` каждого блока
    приложения к `tests/test_invariants.py`, затем `python3 -m pytest
    tests/test_invariants.py` в ней же: код выхода 0. Рабочая копия
    удаляется после прогона.

    Ловит мутацию: вызов `verify-ok`/`verify-fail` в обходе отказывает
    (песочница без ожидания отметки по текущей голове) или не даёт эффекта
    — свойство обхода, проверяющее срабатывание, красное; новая команда
    проходит гейт без решения Оператора — свип «только решения Оператора
    проходят гейт» красный.
    """
    diffs = invariants_diffs()
    scratch = Path(tempfile.mkdtemp(prefix="artel-ac20-"))
    tree = scratch / "tree"
    added = subprocess.run(["git", "-C", str(CODE_ROOT), "worktree", "add",
                            "--detach", str(tree), "HEAD"],
                           capture_output=True, text=True)
    try:
        assert added.returncode == 0, f"рабочая копия HEAD не заведена: {added.stderr}"
        for diff in diffs:
            applied = subprocess.run(["git", "-C", str(tree), "apply"],
                                     input=diff, capture_output=True, text=True)
            assert applied.returncode == 0, f"git apply отказал: {applied.stderr}"
        env = dict(os.environ)
        env.pop("PYTEST_ADDOPTS", None)
        run = subprocess.run([sys.executable, "-m", "pytest", INVARIANTS,
                              "-p", "no:cacheprovider", "-q", "-x"],
                             cwd=str(tree), capture_output=True, text=True,
                             env=env, timeout=SWEEP_TIMEOUT_SEC)
        tail = (run.stdout + run.stderr)[-6000:]
        assert run.returncode == 0, f"обход с приложением красный:\n{tail}"
    finally:
        subprocess.run(["git", "-C", str(CODE_ROOT), "worktree", "remove",
                        "--force", str(tree)], capture_output=True, text=True)
        shutil.rmtree(scratch, ignore_errors=True)
