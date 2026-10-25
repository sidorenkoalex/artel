"""AC-1: патчи мутаций `mutation-<nnn>.diff` и их сопоставление в PLAN.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md в ссылке документов задачи ещё нет — разработчик их не написал.

Источник патчей и PLAN — ссылка документов задачи (`_pult.artifact_text`,
перечень первого уровня — `git ls-tree` ревизии выкладки). Исходный файл
свода `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`
читается из базы ветки (`_pult.DIFF_BASE`): на ветке он удаляется.
Соглашения разбора PLAN — докстринг `_plan.py`: заявка и мутация
сопоставлены, когда строка PLAN (вне таблиц `mutation-run`) несёт
`<Класс>::<метод>` теста и ссылается на патч `mutation-<nnn>` (или
«мутация <n>») сама либо заголовком своего раздела.

Смысловое тождество альтернатив и верность описания правки разбором не
различимы; планка держит наблюдаемую часть: у каждой из 17 заявок есть
мутация, у каждой мутации — заявившие тесты, описание правки с адресом
`orchestrator/…` и фраза о случайности; номера патчей идут в порядке тестов
файла.
"""
import sys
from pathlib import Path

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
    `tests/components_outcome_sandbox.py` — ряд номеров или пути патча
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


def test_ac1_every_claim_mapped_to_mutation():
    """Каждая из 17 заявок исходного файла сопоставлена мутации в PLAN.

    Из базы ветки разбирается исходный файл; тестов со строкой «Ловит
    мутацию» в докстринге — 17. Для каждого в PLAN есть строка вне таблиц с
    `<Класс>::<метод>` теста, ссылающаяся на патч набора.

    Ловит мутацию: PLAN сопоставляет мутации тестам бывших `Ac16`…`Ac22`, а
    заявки `Ac19ForeignPlankTest::…`/`Ac27OutOfBoundsForeignTest::…`
    забыты — перечень несопоставленных непуст, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    mapped = _ctx.mapping(plan, set(_ctx.patch_names()))
    need = [t for t in _ctx.base_tests().values() if t.claim]
    assert len(need) == _plan.CLAIMS, (
        f"в {_plan.SOURCE} базы заявок {len(need)}, а критерий называет "
        f"{_plan.CLAIMS} — база прочитана не та")
    missing = [f"{t.path}::{t.key}" for t in need if not mapped.get(t.key)]
    assert not missing, ("заявки без сопоставленной мутации в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_mutation_has_claim_change_and_randomness_note():
    """У каждой мутации в PLAN названы заявивший тест, что меняет патч и обоснование независимости от случайности.

    Для каждого патча набора: есть строка PLAN вне таблиц, ссылающаяся на
    него, с `<Класс>::<метод>` теста исходного файла базы; есть
    ссылающаяся на него строка с путём `orchestrator/…` (адрес правки:
    модуль и функция); есть ссылающаяся на него строка со словом
    «случайн…» или «зерн…» (фраза обоснования).

    Ловит мутацию: роль добавила патч в набор, но в PLAN не назвала, чью
    заявку он воплощает, не описала правку с адресом в `orchestrator/` или
    пропустила фразу о том, почему исход не зависит от случайных имён и
    `broken`/`other`, — тест краснеет с номером.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    tests = set(_ctx.base_tests())
    claimed, described, justified = set(), set(), set()
    for line, hit in _plan.ref_lines(plan):
        hit &= numbers
        if not hit:
            continue
        if _plan.test_keys(line) & tests:
            claimed |= hit
        if "orchestrator/" in line:
            described |= hit
        if _plan.random_justified(line):
            justified |= hit
    problems = []
    for what, got in (("заявившего теста исходного файла", claimed),
                      ("описания правки с путём orchestrator/…", described),
                      ("обоснования независимости от случайности", justified)):
        lost = sorted(numbers - got)
        if lost:
            problems.append(f"мутации без {what} в PLAN: {lost}")
    assert not problems, "\n".join(problems)


def test_ac1_patch_numbers_follow_test_order_of_file():
    """Номера патчей идут в порядке тестов файла: мутации, впервые заявленные тестом, номерами старше всех мутаций предыдущих тестов.

    Тесты исходного файла базы берутся в порядке текста; у каждого — его
    мутации по сопоставлению PLAN. Мутации теста, не заявленные ни одним
    предыдущим тестом (общая мутация одинаковых по смыслу альтернатив
    разных заявок считается заявленной первым тестом), все больше
    наибольшего номера мутаций предыдущих тестов.

    Ловит мутацию: разработчик пронумеровал сначала мутации бывших `Ac19`…
    `Ac27` (001…), а мутации `Ac16DiffComponentsTest` — после них — новая
    мутация теста младше уже встреченных, тест краснеет с тестом и номером.
    """
    plan = _ctx.plan_text()
    mapped = _ctx.mapping(plan, set(_ctx.patch_names()))
    order = _plan.base_tests(_plan.SOURCE, _ctx.base_text(_plan.SOURCE))
    seen, wrong = set(), []
    for test in order:
        new = mapped.get(test.key, set()) - seen
        if seen and new and min(new) < max(seen):
            wrong.append(f"{test.key}: мутации {sorted(new)} младше уже встреченных "
                         f"(наибольшая {max(seen)})")
        seen |= new
    assert seen, "ни одному тесту исходного файла не сопоставлена мутация"
    assert not wrong, "номера патчей не в порядке тестов файла:\n" + "\n".join(wrong)
