"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходные файлы
волны читаются из базы ветки (`_pult.DIFF_BASE`): на ветке они удаляются.
Соглашения разбора PLAN — докстринг `_plan.py`: тест и мутация
сопоставлены, когда в одной строке PLAN (вне таблиц `mutation-run`) стоят
`<Класс>::<метод>` теста и имя патча `mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество строк «Ловит мутацию» («одинаковые по смыслу — одна
мутация») и верность описания правки разбором не различимы; планка держит
наблюдаемую часть: у каждой из 53 заявок есть мутация, у каждой мутации
есть заявка, одной мутации можно сопоставить список тестов (в одной строке
PLAN — несколько ссылок на тесты).
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


def test_ac1_patches_numbered_in_a_row_and_touch_only_orchestrator():
    """Патчи первого уровня: номера подряд, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи: номера образуют непрерывный ряд; каждый патч несёт хотя бы один
    путь и хотя бы одну изменённую строку, и все его пути — под
    `orchestrator/`.

    Ловит мутацию: разработчик пропустил номер при переписывании набора
    (есть 001, 002, 004) или положил в патч правку `tests/` — перечень/патч
    отличается, тест краснеет с номерами или именем патча.
    """
    names = _patch_names()
    numbers = sorted(names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), (
        f"номера патчей не подряд: {numbers}")
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


def test_ac1_every_one_of_53_claims_mapped_to_mutation():
    """Каждый из 53 тестов трёх исходных файлов со строкой «Ловит мутацию» сопоставлен мутации.

    Из базы ветки разбираются три исходных файла; тестов со строкой
    «Ловит мутацию» в докстринге — 53 (литералы `CLAIM` вне докстрингов не
    считаются). Для каждого в PLAN есть строка вне таблиц, где
    `<Класс>::<метод>` теста стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставляет мутации тестам двух файлов, а
    `tests/test_outcome_integrity.py` (или один тест `Ac7RerunPrepareTest`)
    забыт — перечень несопоставленных непуст, тест краснеет с ним.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    mapped = _mapping(plan, set(_patch_names()))
    need = [t for t in _base_tests() if t.claim]
    assert len(need) == _plan.CLAIM_COUNT, (
        f"в исходных файлах базы заявок {len(need)}, а критерий называет "
        f"{_plan.CLAIM_COUNT} — база прочитана не та")
    missing = [f"{t.path}::{t.key}" for t in need if not mapped.get(t.key)]
    assert not missing, ("тесты без сопоставленной мутации в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_mutation_named_with_its_claiming_tests():
    """У каждой мутации набора в PLAN названы заявившие её тесты исходных файлов.

    Для каждого патча набора есть строка PLAN вне таблиц со ссылкой на него
    и хотя бы одним `<Класс>::<метод>` теста трёх исходных файлов базы;
    тесты с той же мутацией могут стоять списком в одной строке.

    Ловит мутацию: роль добавила патч в набор, но в PLAN не назвала, чью
    строку «Ловит мутацию» он воплощает (или сослалась на несуществующий
    тест) — у номера нет заявивших тестов, тест краснеет с ним.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    numbers = set(_patch_names())
    keys = {t.key for t in _base_tests()}
    named = set()
    for key, hit in _mapping(plan, numbers).items():
        if key in keys:
            named |= hit
    orphan = sorted(numbers - named)
    assert not orphan, ("мутации без заявивших тестов исходных файлов в PLAN: "
                        f"{orphan}")
