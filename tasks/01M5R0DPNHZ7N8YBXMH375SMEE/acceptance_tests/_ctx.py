"""Загрузчики планки поверх помощника пульта `_pult.py`: PLAN, патчи и копии
таблиц из ссылки документов задачи, исходные файлы волны и прежние версии
приёмников из базы ветки (`DIFF_BASE`), приёмники из HEAD рабочей копии.

Загрузчик, не нашедший своего объекта, бросает `LookupError` с причиной —
тест падает с ней (до свода PLAN, патчей и приёмников нет)."""
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


def plan_or_empty() -> str:
    try:
        return artifact_text("PLAN.md") or ""
    except Exception:  # noqa: BLE001 — нет PLAN: сопоставление только по имени
        return ""


def docs_entries() -> list:
    return _plan.docs_entries(DOCS_REPO, DOCS_REVISION, TASK_ID)


def docs_typed_entries() -> list:
    return _plan.docs_typed_entries(DOCS_REPO, DOCS_REVISION, TASK_ID)


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


def copy_tables() -> list:
    """Таблицы всех копий `mutation-run-<n>.tsv` каталога документов."""
    found = []
    for name in docs_entries():
        if _plan.COPY_NAME.match(name):
            tables, _errors = _plan.tables(artifact_text(name) or "")
            found += tables
    return found


def base() -> str:
    if not DIFF_BASE:
        raise LookupError("база диффа ветки задачи не определена при выкладке")
    return DIFF_BASE


def base_text(path: str) -> str:
    text = _plan.show(CODE_ROOT, base(), path)
    if text is None:
        raise LookupError(f"{path} нет в базе ветки {base()}")
    return text


def base_tree(path: str) -> ast.Module:
    return ast.parse(base_text(path))


def head_text(path: str) -> str:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    if text is None:
        raise LookupError(f"{path} нет в HEAD ветки")
    return text


def head_tree(path: str) -> ast.Module:
    return ast.parse(head_text(path))


def base_tests() -> dict:
    """{`<Класс>::<метод>`: BaseTest} двух исходных файлов базы."""
    tests = {}
    for path in _plan.SOURCE_FILES:
        for test in _plan.base_tests(path, base_text(path)):
            tests[test.key] = test
    return tests


def section_text(plan: str, title: str) -> str:
    texts = _plan.sections(plan, title)
    if not texts:
        raise LookupError(f"в PLAN нет раздела «{title}»")
    return "\n".join(texts)


def section_tables(plan: str, title: str) -> list:
    found, errors = _plan.tables(section_text(plan, title))
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


def patch_groups(plan: str, numbers: set) -> dict:
    """{номер мутации: группы} по исходным файлам заявивших её тестов."""
    tests = base_tests()
    groups = {}
    for key, hit in mapping(plan, numbers).items():
        if key in tests:
            for number in hit:
                groups.setdefault(number, set()).add(
                    _plan.GROUP_OF_SOURCE[tests[key].path])
    return groups


def matches(funcs: dict, target: str, cls: str, method: str,
            transfer: dict) -> list:
    """Функции приёмника `target`, в которые перенесён `cls::method`: то же
    имя, имя с суффиксом `_…` или соответствие «до → после» PLAN."""
    names = {n for n in funcs if n == method or n.startswith(method + "_")}
    names |= {func for path, func in transfer.get(f"{cls}::{method}", set())
              if path == target} & set(funcs)
    return [funcs[n] for n in sorted(names)]


def removed_keys(plan: str) -> dict:
    """{ключ теста: номера мутаций} из строк разделов «…дубл…»."""
    removed = {}
    for text in _plan.sections(plan, "дубл"):
        for line in _plan.prose_lines(text):
            for key in _plan.test_keys(line):
                removed.setdefault(key, set()).update(_plan.refs(line))
    return removed


def new_functions(path: str) -> dict:
    """{имя: функция} верхнего уровня приёмника на HEAD, которых нет в его
    версии на базе (для нового файла — все)."""
    head = _plan.module_functions(head_tree(path))
    old = _plan.show(CODE_ROOT, base(), path)
    if old is None:
        return head
    before = set(_plan.module_functions(ast.parse(old)))
    return {n: f for n, f in head.items() if n not in before}
