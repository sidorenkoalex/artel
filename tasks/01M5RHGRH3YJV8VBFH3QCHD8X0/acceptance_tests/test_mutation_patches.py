"""AC-1: патчи мутаций `mutation-<nnn>.diff` и сопоставление в PLAN каждой
из 33 заявок «Ловит мутацию» шести файлов волны патчу.

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
различимы — это сверяет ревьюер и независимая проверка (требование 17).
Планка держит наблюдаемую часть: номера и пути патчей, каждый из 33
тестов сопоставлен патчу, у каждого патча есть заявивший тест, прежний
файл и строка PLAN, называющая его правку.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402

_ALLOWED_SCRIPT = "scripts/guard.py"


def _order_of(test) -> int:
    return _plan.SOURCE_FILES.index(test.path)


def test_ac1_patches_numbered_from_001_in_a_row_and_touch_only_orchestrator_or_guard():
    """Патчи первого уровня: номера 001, 002, … без пропусков, каждый меняет только `orchestrator/` или `scripts/guard.py`.

    Перечень `mutation-<nnn>.diff` первого уровня каталога документов
    задачи начинается с 1 и не имеет пропусков; каждый патч несёт хотя бы
    один путь и одну изменённую строку, и все его пути — под
    `orchestrator/` либо ровно `scripts/guard.py`.

    Ловит мутацию: роль пропустила номер при переписывании набора (001,
    002, 004), начала с 002, положила в патч правку `tests/` или
    `scripts/codebase_map.py` — перечень или пути патча другие, тест
    краснеет с номерами или именем патча.
    """
    names = _ctx.patch_names()
    numbers = sorted(names)
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"номера патчей не подряд с 001: {numbers}")
    problems = []
    for _number, name in sorted(names.items()):
        text = _ctx.patch_text(name)
        paths = _plan.patch_paths(text)
        outside = sorted(p for p in paths if not p.startswith("orchestrator/")
                         and p != _ALLOWED_SCRIPT)
        if not paths:
            problems.append(f"{name}: в патче нет ни одного пути")
        if outside:
            problems.append(f"{name}: меняет файлы вне orchestrator/ и "
                            f"scripts/guard.py: {outside}")
        if _plan.changed_line_count(text) < 1:
            problems.append(f"{name}: в патче нет изменённых строк")
    assert not problems, "\n".join(problems)


def test_ac1_every_one_of_33_claims_mapped_to_a_patch():
    """Каждый из 33 исходных тестов (у всех — заявка «Ловит мутацию») сопоставлен в PLAN патчу набора.

    В базе ветки у шести файлов волны 33 теста, у каждого строка «Ловит
    мутацию» в докстринге. Для каждого в PLAN есть строка вне таблиц, где
    `<Класс>::<метод>` теста стоит рядом со ссылкой на патч набора.

    Ловит мутацию: PLAN сопоставил мутации тестам `answer`…`status_show`, а
    `DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies`
    (или любой тест `new_declares`) не назвал — перечень несопоставленных
    непуст, тест краснеет с ним.
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


def test_ac1_every_patch_named_with_its_claiming_tests_and_old_file():
    """У каждого патча набора в PLAN названы заявившие его исходные тесты и их прежний файл.

    Для каждого патча есть строка PLAN вне таблиц со ссылкой на него, хотя
    бы одним `<Класс>::<метод>` теста шести исходных файлов базы и именем
    (или коротким именем `answer`/`guard`/`plan`/`spec_gate`/`status_show`/
    `new_declares`) прежнего файла этого теста; тесты одной мутации могут
    стоять списком в одной строке.

    Ловит мутацию: роль добавила патч в набор, но не назвала, чью заявку он
    воплощает (или сослалась на несуществующий тест `CheckTest::
    test_check`), либо не назвала прежний файл — у номера нет заявивших
    тестов с файлом, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    numbers = set(_ctx.patch_names())
    tests = _ctx.base_tests()
    named = set()
    for line in _plan.prose_lines(plan):
        hit = _plan.refs(line) & numbers
        if not hit:
            continue
        for key in _plan.test_keys(line) & set(tests):
            path = tests[key].path
            if Path(path).name in line or _plan.PREFIX[path] in line:
                named |= hit
    orphan = sorted(numbers - named)
    assert not orphan, (f"патчи без строки PLAN с заявившим исходным тестом и "
                        f"его прежним файлом: {orphan}")


def test_ac1_patch_numbers_follow_file_order():
    """Номера патчей идут по порядку файлов `answer`, `guard`, `plan`, `spec_gate`, `status_show`, `new_declares`.

    Для каждого патча берётся первый по порядку файлов прежний файл
    заявивших его тестов (по строкам PLAN); последовательность этих файлов
    по возрастанию номеров патчей не убывает в порядке файлов волны.

    Ловит мутацию: роль пронумеровала мутации `new_declares` раньше
    мутаций `answer` (или вставила мутацию `guard` между мутациями
    `spec_gate`) — порядок файлов по номерам ломается, тест краснеет с
    парой номеров.
    """
    plan = _ctx.plan_text()
    names = _ctx.patch_names()
    tests = _ctx.base_tests()
    mapped = _ctx.mapping(plan, set(names))
    first_file = {}
    for key, hit in mapped.items():
        if key not in tests:
            continue
        for number in hit:
            order = _order_of(tests[key])
            first_file[number] = min(order, first_file.get(number, order))
    assert first_file, "в PLAN нет ни одного сопоставления патча тесту"
    seq = [(n, first_file[n]) for n in sorted(first_file)]
    broken = [f"мутация {a} ({Path(_plan.SOURCE_FILES[fa]).name}) раньше "
              f"мутации {b} ({Path(_plan.SOURCE_FILES[fb]).name})"
              for (a, fa), (b, fb) in zip(seq, seq[1:]) if fb < fa]
    assert not broken, "\n".join(broken)


def test_ac1_every_patch_has_a_plan_line_naming_its_change_file():
    """У каждой мутации в PLAN есть строка, называющая, что меняет патч: ссылка на мутацию и файл её правки.

    Для каждого патча набора есть строка PLAN вне таблиц со ссылкой на
    него и именем одного из файлов, которые он меняет (путь
    `orchestrator/<файл>.py`/`scripts/guard.py` или имя `<файл>.py`).

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
        stems = set(files) | {p.rsplit("/", 1)[-1] for p in files}
        if not any(number in _plan.refs(line) and any(s in line for s in stems)
                   for line in lines):
            problems.append(f"{name}: нет строки PLAN со ссылкой на мутацию и "
                            f"файлом правки из {sorted(files)}")
    assert not problems, "\n".join(problems)
