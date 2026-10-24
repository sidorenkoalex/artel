"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходные файлы
свода (`tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` —
группа М, `tests/test_outcome_integrity_added_lines.py` — группа Д)
читаются из базы ветки (`_pult.DIFF_BASE`): на ветке они удаляются.
Соглашения разбора PLAN — докстринг `_plan.py`: заявка и мутация
сопоставлены, когда в одной строке PLAN (вне таблиц `mutation-run`) стоят
`<Класс>::<метод>` теста и имя патча `mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество заявок и альтернатив и верность описания правки
разбором не различимы; планка держит наблюдаемую часть: у каждой из 25
заявок есть мутация, у каждой мутации — заявившие тесты одной группы,
названная группа и описание правки с адресом `orchestrator/…`; патчи группы
М идут номерами раньше патчей группы Д.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402


def test_ac1_patches_numbered_from_001_and_touch_only_orchestrator():
    """Патчи первого уровня: номера подряд от 001, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи: номера образуют непрерывный ряд с 1; каждый патч несёт хотя бы
    один путь и хотя бы одну изменённую строку, и все его пути — под
    `orchestrator/`.

    Ловит мутацию: разработчик выбросил непригодный патч 007, не
    перенумеровав остальные (001…006, 008…), или положил в патч правку
    `tests/merge_outcome_sandbox.py` — ряд номеров или пути патча
    отличаются, тест краснеет с номерами или именем патча.
    """
    names = _ctx.patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд от 001: {numbers}")
    problems = []
    for _number, name in sorted(names.items()):
        text = _ctx.patch_text(name)
        paths = _plan.patch_paths(text)
        outside = sorted(p for p in paths if not p.startswith("orchestrator/"))
        if not paths:
            problems.append(f"{name}: в патче нет ни одного пути")
        if outside:
            problems.append(f"{name}: меняет файлы вне orchestrator/: {outside}")
        if _plan.changed_line_count(text) < 1:
            problems.append(f"{name}: в патче нет изменённых строк")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac1_every_claim_of_group_mapped_to_mutation(letter):
    """Каждая заявка исходного файла группы (19 у М, 6 у Д) сопоставлена мутации в PLAN.

    Из базы ветки разбирается исходный файл группы; тестов со строкой
    «Ловит мутацию» в докстринге — 19 (`merge_outcome_gate`) или 6
    (`added_lines`). Для каждого в PLAN есть строка вне таблиц, где
    `<Класс>::<метод>` теста стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставляет мутации 19 тестам группы М, а заявки
    `AddedLinesTest::…`/`CodeExceptionRenameTest::…` группы Д забыты (или
    забыт последний класс `Ac14OutOfBoundsTest`) — перечень
    несопоставленных непуст, тест краснеет с ним.
    """
    group = next(g for g in _plan.GROUPS if g.letter == letter)
    plan = _ctx.plan_text()
    mapped = _ctx.mapping(plan, set(_ctx.patch_names()))
    need = [t for t in _plan.base_tests(group.source, _ctx.base_text(group.source))
            if t.claim]
    assert len(need) == group.claims, (
        f"в {group.source} базы заявок {len(need)}, а критерий называет "
        f"{group.claims} — база прочитана не та")
    missing = [f"{t.path}::{t.key}" for t in need if not mapped.get(t.key)]
    assert not missing, ("заявки без сопоставленной мутации в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_mutation_has_claims_of_one_group_and_change():
    """У каждой мутации в PLAN названы заявившие тесты одной группы и что меняет патч.

    Для каждого патча набора есть строка PLAN вне таблиц со ссылкой на него
    и `<Класс>::<метод>` хотя бы одного теста исходных файлов базы; все
    заявившие его тесты — из одного исходного файла (одной группы).
    Кроме того, ссылка на патч стоит хотя бы в одной строке PLAN вне
    таблиц, где есть путь `orchestrator/…` — адрес правки патча.

    Ловит мутацию: роль добавила патч в набор, но в PLAN не назвала, чью
    заявку он воплощает (или сопоставила один патч тестам обеих групп), либо
    не описала правку с адресом в `orchestrator/` — тест краснеет с
    номером.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    groups = _ctx.patch_groups(plan, numbers)
    orphan = sorted(numbers - set(groups))
    assert not orphan, ("мутации без заявивших тестов исходных файлов в PLAN: "
                        f"{orphan}")
    mixed = sorted(n for n, g in groups.items() if len(g) > 1)
    assert not mixed, f"мутации с заявками обеих групп: {mixed}"
    described = set()
    for line in _plan.prose_lines(plan):
        if "orchestrator/" in line:
            described |= _plan.refs(line) & numbers
    undescribed = sorted(numbers - described)
    assert not undescribed, ("мутации без описания правки (строка со ссылкой на "
                             f"патч и путём orchestrator/…) в PLAN: {undescribed}")


def test_ac1_group_named_and_m_patches_before_d_patches():
    """Группа каждой мутации названа в PLAN и равна группе её заявок; патчи группы М идут номерами раньше патчей группы Д.

    Группа мутации по заявкам — исходный файл заявивших её тестов. Группа,
    названная в PLAN, — «группа М»/«группа Д» в строке со ссылкой на
    мутацию или в заголовке её раздела; названа ровно одна и она та же,
    что по заявкам. Наибольший номер патча группы М меньше наименьшего
    номера патча группы Д.

    Ловит мутацию: разработчик пронумеровал патчи `added_lines` 001…006, а
    патчи `merge_outcome_gate` — с 007, или не назвал в PLAN группу у
    мутации — тест краснеет с номерами.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    groups = _ctx.patch_groups(plan, numbers)
    named = _plan.group_marks(plan)
    problems = []
    for number in sorted(numbers):
        want = {g.letter for g in groups.get(number, set())}
        got = named.get(number, set())
        if len(got) != 1 or got != want:
            problems.append(f"мутация {number}: группа в PLAN {sorted(got)}, по "
                            f"заявкам {sorted(want)}")
    by_letter = {g.letter: sorted(n for n, gs in groups.items() if g in gs)
                 for g in _plan.GROUPS}
    m, d = by_letter["М"], by_letter["Д"]
    assert m and d, f"патчей группы М {m}, группы Д {d} — нужны обе"
    if max(m) > min(d):
        problems.append(f"патчи группы М {m} не все раньше патчей группы Д {d}")
    assert not problems, "\n".join(problems)
