"""Загрузчики планки поверх помощника пульта `_pult.py`: PLAN и патчи из
ссылки документов задачи, исходные файлы волны из базы ветки
(`DIFF_BASE`), файлы модулей из HEAD рабочей копии.

Загрузчик, не нашедший своего объекта, бросает `LookupError` с причиной —
тест падает с ней (до свода PLAN, патчей и файлов модулей нет)."""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text)


def plan_text() -> str:
    plan = artifact_text("PLAN.md")
    if plan is None:
        raise LookupError("PLAN.md в ссылке документов задачи нет")
    return plan


def docs_entries() -> dict:
    return _plan.docs_entry_types(DOCS_REPO, DOCS_REVISION, TASK_ID)


def patch_names() -> dict:
    names = _plan.patch_names(docs_entries())
    if not names:
        raise LookupError("в каталоге документов задачи первым уровнем нет ни "
                          "одного патча mutation-<nnn>.diff")
    return names


def patch_text(name: str) -> str:
    text = artifact_text(name)
    if text is None:
        raise LookupError(f"{name} не читается из ссылки документов")
    return text


def base() -> str:
    if not DIFF_BASE:
        raise LookupError("база диффа ветки задачи не определена при выкладке")
    return DIFF_BASE


def base_text(path: str) -> str:
    text = _plan.show(CODE_ROOT, base(), path)
    if text is None:
        raise LookupError(f"{path} нет в базе ветки {base()}")
    return text


def base_texts() -> dict:
    return {path: base_text(path) for path in _plan.SOURCE_FILES}


def base_trees() -> dict:
    return {path: ast.parse(text) for path, text in base_texts().items()}


def base_tests() -> dict:
    """{`<Класс>::<метод>`: BaseTest} трёх исходных файлов базы."""
    tests = {}
    for path, text in base_texts().items():
        for test in _plan.base_tests(path, text):
            tests[test.key] = test
    return tests


def head_text(path: str) -> str:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    if text is None:
        raise LookupError(f"{path} нет в HEAD ветки")
    return text


def head_trees() -> dict:
    return {path: ast.parse(head_text(path)) for path in _plan.MODULE_FILES}


def section_tables(plan: str, title: str) -> list:
    texts = _plan.sections(plan, title)
    if not texts:
        raise LookupError(f"в PLAN нет раздела «{title}»")
    found, errors = _plan.tables("\n".join(texts))
    if errors:
        raise LookupError(f"раздел «{title}»: " + "; ".join(errors))
    if not found:
        raise LookupError(f"в разделе «{title}» нет ни одной таблицы "
                          f"mutation-run (шапка «# mutation-run №…»)")
    return found


def mapping(plan: str, numbers: set) -> dict:
    """{ключ исходного теста: номера мутаций} по строкам PLAN вне таблиц."""
    mapped = {}
    for line in _plan.prose_lines(plan):
        hit = _plan.refs(line) & numbers
        if hit:
            for key in _plan.test_keys(line):
                mapped.setdefault(key, set()).update(hit)
    return mapped
