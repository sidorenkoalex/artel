"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходные файлы
свода (`id_mandate`, `test_outcome_integrity`) читаются из базы ветки
(`_pult.DIFF_BASE`): на ветке они удаляются. Соглашения разбора PLAN —
докстринг `_plan.py`: заявка и мутация сопоставлены, когда в одной строке
PLAN (вне таблиц `mutation-run`) стоят `<Класс>::<метод>` теста и имя
патча `mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество заявок («одинаковые по смыслу — одна мутация») и
верность описания правки разбором не различимы; планка держит наблюдаемую
часть: у каждой из 11 заявок есть мутация, у каждой мутации есть заявка,
одной мутации можно сопоставить список тестов (в одной строке PLAN —
несколько ссылок на тесты), у каждой мутации есть строка с описанием.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text)


def _patch_names() -> dict:
    names = _plan.patch_names(
        _plan.docs_entries(DOCS_REPO, DOCS_REVISION, TASK_ID))
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
    found = []
    for path in _plan.SOURCE_FILES:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        found += _plan.base_tests(path, text)
    return found


def test_ac1_patches_numbered_from_001_and_touch_only_orchestrator():
    """Патчи первого уровня: номера подряд от 001, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи: номера образуют непрерывный ряд, начинающийся с 1; каждый патч
    несёт хотя бы один путь и хотя бы одну изменённую строку, и все его
    пути — под `orchestrator/`.

    Ловит мутацию: разработчик взял нумерацию заготовки 2а-1 (набор
    начинается не с 001) или пропустил номер (001, 002, 004), либо положил
    в патч правку `tests/` — перечень/патч отличается, тест краснеет с
    номерами или именем патча.
    """
    names = _patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд от 001: {numbers}")
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


def test_ac1_every_one_of_11_claims_mapped_to_mutation():
    """Каждая из 11 заявок двух исходных файлов сопоставлена мутации в PLAN.

    Из базы ветки разбираются `id_mandate` и `test_outcome_integrity.py`;
    тестов со строкой «Ловит мутацию» в докстринге — 11 (литерал `CLAIM`
    вне докстрингов не считается). Для каждого в PLAN есть строка вне
    таблиц, где `<Класс>::<метод>` теста стоит рядом со ссылкой на патч
    набора.

    Ловит мутацию: PLAN сопоставляет мутации тестам `id_mandate`, а
    `RecordLevelTest::test_skip_growth_line` (или весь
    `test_outcome_integrity.py`) забыт — перечень несопоставленных непуст,
    тест краснеет с ним.
    """
    plan = _plan_text()
    mapped = _mapping(plan, set(_patch_names()))
    need = [t for t in _base_tests() if t.claim]
    assert len(need) == _plan.CLAIM_COUNT, (
        f"в исходных файлах базы заявок {len(need)}, а критерий называет "
        f"{_plan.CLAIM_COUNT} — база прочитана не та")
    missing = [f"{t.path}::{t.key}" for t in need if not mapped.get(t.key)]
    assert not missing, ("заявки без сопоставленной мутации в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_mutation_named_with_its_claims_and_change():
    """У каждой мутации набора в PLAN названы заявившие её тесты и что меняет патч.

    Для каждого патча набора есть строка PLAN вне таблиц со ссылкой на него
    и хотя бы одним `<Класс>::<метод>` теста двух исходных файлов базы;
    тесты с той же мутацией могут стоять списком в одной строке. Кроме
    того, ссылка на патч стоит хотя бы в одной строке PLAN вне таблиц, где
    есть путь `orchestrator/…` — адрес правки патча.

    Ловит мутацию: роль добавила патч в набор, но в PLAN не назвала, чью
    заявку он воплощает (или сослалась на тест `outcome_gate`, не входящий
    в свод), либо не описала правку с адресом в `orchestrator/` — у номера
    нет заявивших тестов или описания, тест краснеет с ним.
    """
    plan = _plan_text()
    numbers = set(_patch_names())
    keys = {t.key for t in _base_tests()}
    named = set()
    for key, hit in _mapping(plan, numbers).items():
        if key in keys:
            named |= hit
    orphan = sorted(numbers - named)
    assert not orphan, ("мутации без заявивших тестов исходных файлов в PLAN: "
                        f"{orphan}")
    described = set()
    for line in _plan.prose_lines(plan):
        if "orchestrator/" in line:
            described |= _plan.refs(line) & numbers
    undescribed = sorted(numbers - described)
    assert not undescribed, ("мутации без описания правки (строка со ссылкой на "
                             f"патч и путём orchestrator/…) в PLAN: {undescribed}")
