"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление заявкам crg в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходный файл
волны `tests/test_component_report_gates.py` читается из базы ветки
(`_pult.DIFF_BASE`): на ветке он удалён. Соглашения разбора PLAN —
докстринг `_plan.py`: тест и мутация сопоставлены, когда в одной строке
PLAN (вне таблиц `mutation-run`) стоят `<Класс>::<метод>` теста и имя патча
`mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество альтернатив заявки и верность описания правки разбором
не различимы; планка держит наблюдаемую часть: у каждой из 13 заявок есть
патч, у каждого патча есть заявившие его тесты и описание правки.
"""
import keyword
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text)


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entry_types(DOCS_REPO, DOCS_REVISION, TASK_ID))
    assert names, ("в каталоге документов задачи первым уровнем нет ни одного "
                   "патча mutation-<nnn>.diff")
    return names


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _mapping(plan: str, numbers: set) -> dict:
    """{ключ теста: номера мутаций} по строкам PLAN вне таблиц."""
    mapped = defaultdict(set)
    for line in _plan.prose_lines(plan):
        hit = _plan.refs(line) & numbers
        if hit:
            for key in _plan.test_keys(line):
                mapped[key] |= hit
    return mapped


def _base_tests() -> list:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, _plan.SOURCE_FILE)
    assert text is not None, f"{_plan.SOURCE_FILE} нет в базе ветки {DIFF_BASE}"
    return _plan.base_tests(text)


def test_ac1_patches_numbered_from_001_and_touch_only_orchestrator():
    """Патчи первого уровня: номера подряд с 001, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи: номера — ровно 1…N без пропусков; каждый патч несёт хотя бы
    один путь и хотя бы одну изменённую строку, и все его пути — под
    `orchestrator/`.

    Ловит мутацию: разработчик начал нумерацию с 000 или пропустил номер
    при переписывании набора (есть 001, 002, 004), либо положил в патч
    правку `tests/report_outcome_sandbox.py` — перечень/патч отличается,
    тест краснеет с номерами или именем патча.
    """
    names = _patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд с 001: {numbers}")
    problems = []
    for _number, name in sorted(names.items()):
        text = artifact_text(name)
        if text is None:
            problems.append(f"{name}: не читается из ссылки документов")
            continue
        paths = _plan.patch_paths(text)
        outside = sorted(p for p in paths if not p.startswith("orchestrator/"))
        if not paths:
            problems.append(f"{name}: в патче нет ни одного пути")
        if outside:
            problems.append(f"{name}: меняет файлы вне orchestrator/: {outside}")
        if _plan.changed_line_count(text) < 1:
            problems.append(f"{name}: в патче нет изменённых строк")
    assert not problems, "\n".join(problems)


def test_ac1_every_one_of_13_claims_mapped_to_patch():
    """Каждый из 13 тестов crg со строкой «Ловит мутацию» сопоставлен в PLAN патчу набора.

    Из базы ветки разбирается crg; тестов со строкой «Ловит мутацию» — 13.
    Для каждого в PLAN есть строка вне таблиц, где `<Класс>::<метод>` теста
    стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставляет патчи двенадцати тестам, а
    `EmptyInstallTest::test_empty_install_neither_installs_nor_refuses`
    забыт — перечень несопоставленных непуст, тест краснеет с ним.
    """
    plan = _plan_text()
    mapped = _mapping(plan, set(_patch_names()))
    need = [t for t in _base_tests() if t.claim]
    assert len(need) == _plan.CLAIM_COUNT, (
        f"в crg базы заявок {len(need)}, а критерий называет "
        f"{_plan.CLAIM_COUNT} — база прочитана не та")
    missing = [t.key for t in need if not mapped.get(t.key)]
    assert not missing, ("тесты crg без сопоставленного патча в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_patch_named_with_claiming_test_and_change():
    """У каждого патча набора в PLAN названы заявивший тест crg и то, что патч меняет.

    Для каждого патча есть строка PLAN вне таблиц со ссылкой на него и
    хотя бы одним `<Класс>::<метод>` теста crg базы; в строках PLAN со
    ссылкой на патч упомянут путь `orchestrator/…` или имя функции/константы
    из его изменённых строк (описание правки).

    Ловит мутацию: роль добавила патч в набор, но в PLAN не назвала, чью
    заявку он воплощает и что меняет (или сослалась на несуществующий
    тест) — у номера нет заявивших тестов или описания, тест краснеет с
    ним.
    """
    plan = _plan_text()
    names = _patch_names()
    keys = {t.key for t in _base_tests()}
    named = set()
    for key, hit in _mapping(plan, set(names)).items():
        if key in keys:
            named |= hit
    orphan = sorted(set(names) - named)
    assert not orphan, ("патчи без заявившего теста crg в PLAN: "
                        f"{orphan}")
    lines = _plan.prose_lines(plan)
    undescribed = []
    for number, name in sorted(names.items()):
        text = artifact_text(name) or ""
        words = {p for p in _plan.patch_paths(text)}
        words |= {Path(p).name for p in words}
        words |= {w for line in text.splitlines()
                  if line[:1] in "+-" and not line.startswith(("+++", "---"))
                  for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", line)
                  if w not in keyword.kwlist and w not in ("self", "None", "True")}
        mine = [line for line in lines if number in _plan.refs(line)]
        if not any(w in line for line in mine for w in words):
            undescribed.append(name)
    assert not undescribed, ("у патчей нет описания правки в PLAN (ни пути, "
                             "ни имени из изменённых строк): "
                             + ", ".join(undescribed))
