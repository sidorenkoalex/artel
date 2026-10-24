"""AC-1: патчи мутаций `mutation-<nnn>.diff` и сопоставление в PLAN каждой
из 37 заявок «Ловит мутацию» пяти файлов волны патчу.

Группа: разовый
Красен до реализации: патчей mutation-<nnn>.diff и PLAN.md ещё нет — загрузчики _ctx бросают LookupError.

Патчи и PLAN — ссылка документов задачи (`_pult.artifact_text`, перечень
первого уровня — `git ls-tree` ревизии выкладки); исходные файлы — база
ветки (`_pult.DIFF_BASE`). Соглашения разбора PLAN — докстринг
`_plan.py`: тест и мутация сопоставлены, когда в одной строке PLAN (вне
таблиц `mutation-run`) стоят `<Класс>::<метод>` теста и имя патча
`mutation-<nnn>` (или «мутация <n>»).

Смысловое тождество заявок и альтернатив «либо …» («одинаковые по
смыслу — одна мутация») и верность описания правки разбором не
различимы — это сверяет ревьюер и независимая проверка (требование 19).
Планка держит наблюдаемую часть: каждый из 37 тестов сопоставлен патчу,
у каждого патча есть заявивший тест и строка PLAN, называющая его правку.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402


def test_ac1_patches_numbered_from_001_in_a_row_and_touch_only_orchestrator():
    """Патчи первого уровня: номера 001, 002, … без пропусков, каждый меняет только `orchestrator/`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи начинается с 1 и не имеет пропусков; каждый патч несёт хотя бы
    один путь и одну изменённую строку, и все его пути — под
    `orchestrator/`.

    Ловит мутацию: роль пропустила номер при переписывании набора (001,
    002, 004), начала с 002 или положила в патч правку `tests/` — перечень
    или пути патча другие, тест краснеет с номерами или именем патча.
    """
    names = _ctx.patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд с 001: {numbers}")
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


def test_ac1_every_one_of_37_claims_mapped_to_a_patch():
    """Каждый из 37 исходных тестов (у всех — заявка «Ловит мутацию») сопоставлен в PLAN патчу набора.

    В базе ветки у пяти файлов волны 37 тестов, у каждого строка «Ловит
    мутацию» в докстринге. Для каждого в PLAN есть строка вне таблиц, где
    `<Класс>::<метод>` теста стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставил мутации тестам mutex_by_project, а
    `DeclaredPathTest::test_ac9_escalated_answer_unblocks_same_spec_and_
    other_refusals_unchanged` (или любой тест merge_after) не назвал —
    перечень несопоставленных непуст, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    mapped = _ctx.mapping(plan, set(_ctx.patch_names()))
    tests = _ctx.base_tests()
    assert len(tests) == _plan.TEST_COUNT, (
        f"в исходных файлах базы тестов {len(tests)}, критерий называет "
        f"{_plan.TEST_COUNT} — база прочитана не та")
    claims = sum(1 for t in tests.values() if t.claim)
    assert claims == _plan.CLAIM_COUNT, (
        f"в исходных файлах базы заявок {claims}, критерий называет "
        f"{_plan.CLAIM_COUNT}")
    missing = [f"{t.path}::{t.key}" for t in tests.values() if not mapped.get(t.key)]
    assert not missing, ("исходные тесты без сопоставленного патча в PLAN:\n"
                         + "\n".join(missing))


def test_ac1_every_patch_named_with_its_claiming_tests():
    """У каждого патча набора в PLAN названы заявившие его исходные тесты.

    Для каждого патча есть строка PLAN вне таблиц со ссылкой на него и
    хотя бы одним `<Класс>::<метод>` теста пяти исходных файлов базы;
    тесты одной мутации могут стоять списком в одной строке.

    Ловит мутацию: роль добавила патч в набор, но не назвала, чью заявку он
    воплощает (или сослалась на несуществующий тест `CheckTest::
    test_check`) — у номера нет заявивших тестов, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    keys = set(_ctx.base_tests())
    named = set()
    for key, hit in _ctx.mapping(plan, numbers).items():
        if key in keys:
            named |= hit
    orphan = sorted(numbers - named)
    assert not orphan, f"патчи без заявивших исходных тестов в PLAN: {orphan}"


def test_ac1_every_patch_has_a_plan_line_naming_its_change_file():
    """У каждой мутации в PLAN есть строка, называющая, что меняет патч: ссылка на мутацию и файл `orchestrator/` её патча.

    Для каждого патча набора есть строка PLAN вне таблиц со ссылкой на
    него и именем одного из файлов, которые он меняет (путь
    `orchestrator/<файл>.py` или имя `<файл>.py`).

    Ловит мутацию: PLAN перечислил мутации номерами со списками тестов, а
    правку патча не описал ни для одной (или описал только часть) — у
    номера нет строки с файлом правки, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    lines = _plan.prose_lines(plan)
    problems = []
    for number, name in sorted(names.items()):
        files = _plan.patch_paths(_ctx.patch_text(name))
        stems = {p for p in files} | {p.rsplit("/", 1)[-1] for p in files}
        if not any(number in _plan.refs(line) and any(s in line for s in stems)
                   for line in lines):
            problems.append(f"{name}: нет строки PLAN со ссылкой на мутацию и "
                            f"файлом правки из {sorted(files)}")
    assert not problems, "\n".join(problems)
