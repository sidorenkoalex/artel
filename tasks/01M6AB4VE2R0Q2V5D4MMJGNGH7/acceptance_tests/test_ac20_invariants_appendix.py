"""Приложение PLAN к `tests/test_invariants.py`: применяется к `base`, добавляет `mr-sync` в обход команд и тест «надзор не закрывает задачу».

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан — `artifact_text("PLAN.md")` даёт `None`, приложения к `tests/test_invariants.py` нет.

Источник — PLAN.md ссылки документов задачи (помощник пульта
`artifact_text`), применимость — `apply_check` к дереву HEAD рабочей
копии (ветка задачи от `base`; сам `tests/test_invariants.py` задача
правит только приложением, поэтому его текст в HEAD — текст `base`).
Приложение — блок ```diff в PLAN.md, заголовок которого называет
`tests/test_invariants.py`.

Стаб корректной реализации не прогонялся: PLAN.md — артефакт
разработчика, планка его не пишет; проверка — разбор блока и
`apply_check` помощника пульта.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import apply_check, artifact_text  # noqa: E402

TARGET = "tests/test_invariants.py"
DIFF_BLOCK = re.compile(r"```diff\n(.*?)```", re.S)

def appendix() -> str | None:
    """Дифф приложения PLAN к `tests/test_invariants.py`; None — его нет."""
    plan = artifact_text("PLAN.md")
    if plan is None:
        return None
    for block in DIFF_BLOCK.findall(plan):
        if f"b/{TARGET}" in block or f"+++ {TARGET}" in block:
            return block
    return None


def added_text(diff: str) -> str:
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def test_ac20_appendix_applies_and_adds_mr_sync_coverage():
    """PLAN несёт приложение к `tests/test_invariants.py`, оно применяется к `base` и добавляет `mr-sync` в обход команд с песочницей `target-human` и тест «надзор не закрывает задачу».

    Сценарий: из PLAN.md ссылки документов взят блок ```diff к
    `tests/test_invariants.py`. `git apply --check` (помощник `apply_check`)
    соглашается наложить его на дерево HEAD. Добавленные строки называют
    `mr-sync` (обход команд), `target-human` и `awaiting_human` (песочница
    обхода с проектом и задачей), `--confirm`, `closed_as` и
    `refs/artifacts` (тест наблюдает состояние, коммит закрытия и
    `closed_as`), а также `auto` и надзор эпика (`epic`).

    Ловит мутацию: приложения нет или оно к другому файлу; дифф не
    применяется (хедер хунка не совпадает с файлом `base`); обход без
    `mr-sync` или без песочницы `target-human`/`awaiting_human` (сверка
    отказала бы пустым набором); тест строки 18 проверяет аргументы
    вызова, а не `closed_as`/коммит закрытия.
    """
    diff = appendix()
    assert diff is not None, f"в PLAN.md нет приложения к {TARGET}"
    refusal = apply_check(diff)
    assert refusal == "", f"приложение не применяется: {refusal}"
    added = added_text(diff)
    for word in ("mr-sync", "target-human", "awaiting_human", "--confirm",
                 "closed_as", "refs/artifacts", "auto", "epic"):
        assert word in added, f"добавленные строки не называют {word!r}"
