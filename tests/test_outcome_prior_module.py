"""Тесты гейта неослабления по исходам G3б-2 на стенде `PriorSandbox`:
прежние версии изменённых тестов на коде ветки (третья выписка, набор C,
перепрогоны, находки «прежняя версия красная/нестабильна на коде ветки»,
удаление добавленных файлов тестов и поддержки), сбои подготовки и граница
гейта (волна 2а-2в-1 сведения тестов, SPEC 01M5RS4CRRFNC5SG4PBQFQWXDT;
ADR-0027 п. 8, ADR-0020 п. 8).

Свод 22 тестов долгоживущего
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` (классы `Ac3` …
`Ac13`, `Ac32`, `Ac33`, `Ac30` SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J):
долгоживущий файл сокращён решением Оператора (ADR-0020 п. 8), свойства
перенесённых тестов — здесь; остальные его тесты (стенды
`ReplacementSandbox` и `StrictSandbox`) сводятся задачей 2а-2в-2.
Доказательство неослабления — таблицы `mutation-run` «до» и «после» в PLAN
задачи.

Стенд `box` — `tests.prior_outcome_sandbox.PriorSandbox` поверх песочницы
гейта исходов G3а-1а и её надстройки гейта мержа
(`tests.merge_outcome_sandbox.MergeOutcomeSandbox` поверх
`tests.outcome_gate_sandbox.OutcomeGateSandbox`): настоящий git, учебный
внешний проект с единственным компонентом `junit-xml` на поддельном
`pytest` (`python-ast` по умолчанию), раннер подменён шпионом
`subprocess.Popen`, исход теста задаётся сценарием по стороне прогона.

Сторона «прежние версии» (`OLD`): дерево прогона — выписка головы
(`app.py` с меткой головы) в каталоге `scratch` гейта (рядом лежит маркер
владельца `liveness.GATE_OWNER_MARKER`), имя каталога выписки — не `base`
и не `head`. Исход теста на этой стороне — последовательность сценария
`cases[(путь, имя)][OLD]` (по умолчанию `passed`); «спасатель» `rescue` —
пути, при наличии которых в дереве прогона прежняя версия зелёная
(подмена сломанной функции добавленным `conftest.py`). Шпион
`subprocess.run` записывает каждую `worktree add` из кадров модуля гейта
(путь и наличие маркера владельца рядом в момент вызова) и, по правилу
сценария `git_fail`, отвечает отказом git.

Мандат Оператора — `answer.cmd_answer` с маркером и матрицей
неослабления (помощник `grant`). Помощники, утверждающие исход, —
функции модуля `refusal`, `no_gate_refusal`, `passed`, `conftest_case`
(первый параметр — стенд; у первых трёх последний — `case`: ярлык
подслучая и зерно спереди к тексту каждого сообщения). Бывшие `subTest` —
прежним циклом или прямым кодом в одной функции, ярлык подслучая и зерно —
в локальном `case`.

Имена проектов, файлов, тестов, позиции строк и выбор исходов — из
`random`; зерно печатается и входит в текст каждого провала.
"""
import os

import pytest

from tests.fixtures import _sandbox
from tests.outcome_gate_sandbox import GATE_ACTIONS, flow, py_source
from tests.prior_outcome_sandbox import (
    FILE_ERROR_MARK, FLAKY, OLD, OUTCOME_ACTION, PASSED_ACTION, PREPARE_ACTION,
    PRIOR_LINE, PRIOR_RED, PRIOR_UNSTABLE, SIDES, SKIPPED, Link, Moved,
    PriorSandbox)


@pytest.fixture
def box():
    """Стенд PriorSandbox после setUp."""
    yield from _sandbox(PriorSandbox)


# ---------------------------------------------------------------- помощники


def refusal(box, rows: list, output: str, action: str, case: str = "") -> str:
    """Деталь последней записи `action`; провал — записи нет, есть
    запись другого действия гейта исходов, либо задача ушла из
    `in_dev`."""
    found = box.details(rows, action)
    box.assertTrue(found, case + f"advance не записал «{action}»:\n"
                    + box.explain(rows, output))
    others = [a for a in GATE_ACTIONS if a != action and box.details(rows, a)]
    box.assertEqual(others, [], case + box.explain(rows, output))
    box.assertEqual(box.state_of(rows), "in_dev", case + box.explain(rows, output))
    return found[-1]


def no_gate_refusal(box, rows: list, output: str, case: str = "") -> None:
    for action in GATE_ACTIONS:
        box.assertEqual(box.details(rows, action), [],
                         case + box.explain(rows, output))


def passed(box, rows: list, output: str, case: str = "") -> str:
    """Деталь последней записи пройденного гейта; провал — записи нет."""
    found = box.details(rows, PASSED_ACTION)
    box.assertTrue(found, case + f"записи «{PASSED_ACTION}» нет:\n"
                   + box.explain(rows, output))
    return found[-1]


def grant(box, t, paths=(), ids=(), covered="tests/sandbox.py:1", case: str = "") -> None:
    """Мандат Оператора `answer` на `paths`/`ids`; отказ команды — провал
    подготовки."""
    ok, output = box.operator_answer(t, paths, ids, covered)
    box.assertTrue(ok, case + box.note(f"answer отказала: {output}"))


def conftest_case(box, extra: dict | None, conftest: str):
    """Ветка добавляет `conftest`, «чинящий» прежнюю версию изменённого
    теста (на стороне прежних версий тест зелёный, только если файл
    есть в дереве): ожидается отказ с находкой прежней версии и
    отсутствие файла на третьей выписке."""
    rel, name = box.py_rel(), box.py_name()
    project = box.junit({rel: [name]}, extra=extra)
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"], OLD: ["failed"]}
    box.rescue = (conftest,)
    box.watch_old = (conftest,)
    rows, output = box.developer_advance(t, {
        conftest: "import app\n\napp.fixed = True\n", rel: box.edited_py([name])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    cid = box.case_id(project, rel, name)
    box.assertTrue(box.starting(detail, f"{PRIOR_RED}: {cid} — "),
                   box.explain(rows, output))
    box.assertTrue(box.old_runs(), box.explain(rows, output))
    box.assertFalse(any(r["seen"][conftest] for r in box.old_runs()),
                    box.explain(rows, output))


# ---------------------------------------------------------------- тесты


def test_ac3_green_prior_version_passes_with_prior_line(box):
    """Изменённые файлы тестов, прежние версии которых зелёные на коде ветки, находок не дают: гейт пройден, запись несёт «прежние версии: файлов <n>; прогонов <m>».

    Сценарий: проект `junit-xml`, один или два (из `random`) файла
    тестов базы изменены веткой (тесты прежние, добавлена строка
    комментария), ещё один файл не тронут. На стороне прежних версий
    исход по умолчанию — `passed`. Отказа гейта исходов нет; в записи
    пройденного гейта ровно одна строка «прежние версии: …», `n` —
    число изменённых файлов, `m` — число прогонов на стороне прежних
    версий (не меньше одного); на этой стороне гонялись ровно
    изменённые файлы.

    Ловит мутацию: третья выписка не делается — прогонов на стороне
    прежних версий нет и строки нет; строка пишется без чисел или
    считает файлы набора C вместе с неизменённым файлом — `n` не тот;
    гоняется весь набор вместо файлов C — на стороне прежних версий
    гонялся и неизменённый файл.
    """
    count = box.rng.randint(1, 2)
    rels = [box.py_rel() for _ in range(count)]
    tests = {rel: [box.py_name(), box.py_name()] for rel in rels}
    tests[box.py_rel()] = [box.py_name()]
    project = box.junit(tests)
    t = box.task(project)
    rows, output = box.developer_advance(
        t, {rel: box.edited_py(tests[rel]) for rel in rels})
    no_gate_refusal(box, rows, output)
    detail = passed(box, rows, output)
    prior = [PRIOR_LINE.match(line) for line in detail.splitlines()]
    prior = [m for m in prior if m]
    assert len(prior) == 1, box.explain(rows, output)
    files, runs = (int(x) for x in prior[0].groups())
    assert files == count, box.explain(rows, output)
    assert runs >= 1, box.explain(rows, output)
    assert runs == len(box.old_runs()), box.explain(rows, output)
    assert box.old_files() == set(rels), box.explain(rows, output)


def test_ac10_empty_set_no_third_checkout(box):
    """Набор C пуст — третьей выписки нет: ни `worktree add` прежних версий, ни прогона, ни строки «прежние версии: …».

    Сценарий: проект `junit-xml`, ветка правит только код (`app.py`) и
    добавляет файл кода вне тестов. Гейт пройден; среди `worktree add`
    гейта нет выписки с каталогом, отличным от `base`/`head`; прогонов
    на стороне прежних версий нет; в записи пройденного гейта нет
    строки «прежние версии: …».

    Ловит мутацию: шаг прежних версий исполняется и при пустом C —
    третья `worktree add` и строка «прежние версии: файлов 0; …» в
    записи.
    """
    project = box.junit({box.py_rel(): [box.py_name()]})
    t = box.task(project)
    rows, output = box.developer_advance(
        t, {f"lib/{box.word()}.py": "VALUE = 1\n"})
    no_gate_refusal(box, rows, output)
    detail = passed(box, rows, output)
    assert box.third_adds() == [], box.explain(rows, output)
    assert box.old_runs() == [], box.explain(rows, output)
    assert not any(PRIOR_LINE.match(line) or line.startswith("прежние версии")
                         for line in detail.splitlines()), (
        box.explain(rows, output))


def test_ac4_prior_red_thrice_refuses_outcome(box):
    """Прежняя версия изменённого теста трижды красная на коде ветки при зелёной базе — отказ «… по исходам» со строкой «прежняя версия красная на коде ветки: <идентификатор> — прежняя версия: …; база: …».

    Сценарий: проект `junit-xml`; тест базы `PASS_TO_PASS`, на голове
    зелёный, его файл изменён веткой (добавлен комментарий); на стороне
    прежних версий тест `failed` во всех прогонах, база зелёна во всех.
    Действие отказа — общее «переход отклонён: гейт неослабления по
    исходам»; ровно одна строка детали с идентификатором, начинается с
    «прежняя версия красная на коде ветки: <id> — прежняя версия: » и
    несёт «; база: ».

    Ловит мутацию: прежние версии не гоняются — переход в `verifying`;
    красная прежняя версия отнесена к «сломан правкой» — действие
    «… — сломан правкой»; исходы строки без «прежняя версия: » или
    без базы — строка другой формы.
    """
    rel, name, other = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit({rel: [name, other]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"],
                               OLD: ["failed"]}
    rows, output = box.developer_advance(t, {rel: box.edited_py([name, other])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    cid = box.case_id(project, rel, name)
    lines = box.lines_with(detail, cid)
    assert len(lines) == 1, box.explain(rows, output)
    assert lines[0].startswith(f"{PRIOR_RED}: {cid} — прежняя версия: "), box.explain(rows, output)
    assert "; база: " in lines[0], box.explain(rows, output)


def test_ac5_prior_mixed_is_unstable_finding(box):
    """Прежняя версия красная и зелёная вперемешку на третьей выписке — находка «прежняя версия нестабильна на коде ветки» и общий отказ.

    Сценарий: проект `junit-xml`, файл теста изменён веткой; на
    стороне прежних версий первый прогон `failed`, перепрогоны — смесь
    `failed`/`passed` (порядок из `random`); база зелёна. Отказ «… по
    исходам», строка детали начинается с «прежняя версия нестабильна на
    коде ветки: <id> — прежняя версия: »; строки «прежняя версия
    красная …» по нему нет.

    Ловит мутацию: смесь исходов отнесена к «красной» — строка «прежняя
    версия красная на коде ветки»; перепрогонов на третьей выписке нет —
    один красный прогон даёт «красная».
    """
    rel, name, other = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit({rel: [name, other]})
    t = box.task(project)
    old = box.rng.choice((["failed", "passed", "failed"],
                           ["failed", "failed", "passed"],
                           ["failed", "passed", "passed"]))
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"], OLD: old}
    rows, output = box.developer_advance(t, {rel: box.edited_py([name, other])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    cid = box.case_id(project, rel, name)
    assert box.starting(detail, f"{PRIOR_UNSTABLE}: {cid} — прежняя версия: "), (
        box.explain(rows, output) + f"\nисходы: {old}")
    assert not box.starting(detail, f"{PRIOR_RED}: {cid}"), box.explain(rows, output)


def test_ac5_red_base_rerun_is_flaky_line_not_finding(box):
    """Прежняя версия красная, база красна в одном из перепрогонов — не находка, а строка «нестабилен и на базе: <идентификатор>» в записи пройденного гейта.

    Сценарий: проект `junit-xml`, файл теста изменён веткой; прежняя
    версия `failed` во всех прогонах; база в полном прогоне зелёна, в
    одном из двух перепрогонов (из `random`) — `failed` или `error`.
    Отказа гейта исходов нет; запись пройденного гейта несёт строку
    «нестабилен и на базе: <id>» и не несёт строки находки прежней
    версии по нему.

    Ловит мутацию: база в перепрогонах прежних версий не гоняется либо
    её краснота не читается — отказ «прежняя версия красная на коде
    ветки»; строка о базе не пишется — её нет в записи.
    """
    rel, name, other = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit({rel: [name, other]})
    t = box.task(project)
    base = ["passed", "passed", "passed"]
    base[box.rng.choice((1, 2))] = box.rng.choice(("failed", "error"))
    box.cases[(rel, name)] = {"base": base, "head": ["passed"], OLD: ["failed"]}
    rows, output = box.developer_advance(t, {rel: box.edited_py([name, other])})
    no_gate_refusal(box, rows, output)
    detail = passed(box, rows, output)
    cid = box.case_id(project, rel, name)
    assert f"{FLAKY}: {cid}" in detail.splitlines(), box.explain(rows, output)
    assert not box.starting(detail, f"{PRIOR_RED}: {cid}"), box.explain(rows, output)


def test_ac6_old_kind_finding_wins_single_line(box):
    """Тест с находкой прежнего вида («стал пропуском»), прежняя версия которого красная на коде ветки, — в детали отказа ровно одна строка с его идентификатором, строка старшей находки.

    Сценарий: проект `junit-xml`, файл теста изменён веткой; тест базы
    зелёный, на голове `skipped`, прежняя версия `failed` во всех
    прогонах. Отказ «… по исходам»: строк с идентификатором — одна, она
    начинается с «стал пропуском: <id> — ».

    Ловит мутацию: находка прежней версии добавляется к находке
    прежнего вида — две строки с идентификатором.
    """
    rel, name, other = box.py_rel(), box.py_name(), box.py_name()
    project = box.junit({rel: [name, other]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"],
                               OLD: ["failed"]}
    rows, output = box.developer_advance(t, {rel: box.edited_py([name, other])})
    detail = refusal(box, rows, output, OUTCOME_ACTION)
    cid = box.case_id(project, rel, name)
    lines = box.lines_with(detail, cid)
    assert len(lines) == 1, box.explain(rows, output)
    assert lines[0].startswith(f"{SKIPPED}: {cid} — "), box.explain(rows, output)


def test_ac7_test_support_change_runs_full_suite(box):
    """Изменён только файл под маской `test_support` — на третьей выписке гоняется полный набор компонента (`fresh`).

    Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
    правит только `support/<имя>.py`. Среди вызовов полного набора есть
    вызов на стороне прежних версий с `fresh=True`; гейт пройден.

    Ловит мутацию: путь `test_support` не входит в C — третьей выписки
    и полного набора на ней нет; при пути `test_support` гоняются
    только файлы C — полного набора на стороне прежних версий нет.
    """
    support = f"support/{box.word()}.py"
    project = box.junit({box.py_rel(): [box.py_name()]},
                         extra={"test_support": flow(["support/**"])},
                         files={support: "HELPER = 1\n"})
    t = box.task(project)
    rows, output = box.developer_advance(t, {support: "HELPER = 2\n"})
    no_gate_refusal(box, rows, output)
    passed(box, rows, output)
    assert any(c["side"] == OLD and c["fresh"] for c in box.suite_calls), box.explain(rows, output)


def test_ac7_tests_change_runs_only_changed_files(box):
    """Изменены только файлы `tests` — на третьей выписке гоняются ровно эти файлы, без полного набора.

    Сценарий: проект `junit-xml` с тремя файлами тестов; ветка правит
    два из них (выбор из `random`). На стороне прежних версий нет
    полного прогона и вызова полного набора, а объединение файлов
    прогонов — ровно два изменённых файла.

    Ловит мутацию: на третьей выписке всегда гоняется полный набор —
    полный прогон на стороне прежних версий; гоняются и неизменённые
    файлы отчёта базы — лишний файл.
    """
    tests = {box.py_rel(): [box.py_name()] for _ in range(3)}
    changed = box.rng.sample(sorted(tests), 2)
    project = box.junit(tests)
    t = box.task(project)
    rows, output = box.developer_advance(
        t, {rel: box.edited_py(tests[rel]) for rel in changed})
    no_gate_refusal(box, rows, output)
    assert box.old_runs(), box.explain(rows, output)
    assert not any(r["full"] for r in box.old_runs()), box.explain(rows, output)
    assert not any(c["side"] == OLD for c in box.suite_calls), box.explain(rows, output)
    assert box.old_files() == set(changed), box.explain(rows, output)


def test_ac8_deleted_file_restored_and_judged(box):
    """Удалённый файл тестов на третьей выписке восстановлен, его тесты базы судятся.

    Сценарий: проект `junit-xml`, два файла тестов; ветка удаляет один
    (мандат Оператора на его путь — исчезновение законно). Гейт пройден;
    на стороне прежних версий гонялся удалённый файл, в записи — «прежние
    версии: файлов 1; …».

    Ловит мутацию: записи `D` выброшены из C — третьей выписки нет;
    удалённый путь не восстанавливается командой `git checkout <база>
    -- <пути>` — файла в прогоне нет.
    """
    gone, keep = box.py_rel(), box.py_rel()
    project = box.junit({gone: [box.py_name()], keep: [box.py_name()]})
    t = box.task(project)
    grant(box, t, paths=[gone])
    rows, output = box.developer_advance(t, {gone: None}, finished=True)
    no_gate_refusal(box, rows, output)
    detail = passed(box, rows, output)
    assert gone in box.old_files(), box.explain(rows, output)
    prior = [PRIOR_LINE.match(line) for line in detail.splitlines()]
    assert [m.group(1) for m in prior if m] == ["1"], box.explain(rows, output)


def test_ac8_renamed_file_old_path_restored_new_stays(box):
    """У переименованного файла тестов на третьей выписке восстановлен прежний путь, новый путь остаётся.

    Сценарий: проект `junit-xml`; ветка переименовывает файл тестов
    (`git mv` без правки строк — статус `R100`), мандат Оператора на оба
    пути. На стороне прежних версий гонялся прежний путь; в момент
    прогона в дереве третьей выписки есть и прежний, и новый путь.

    Ловит мутацию: у `R` берётся новый путь — прежний не восстановлен
    и не гонялся; новый путь удалён с третьей выписки — его нет в
    дереве.
    """
    old_rel, new_rel = box.py_rel(), box.py_rel()
    project = box.junit({old_rel: [box.py_name()], box.py_rel(): [box.py_name()]})
    t = box.task(project)
    grant(box, t, paths=[old_rel, new_rel])
    box.watch_old = (old_rel, new_rel)
    rows, output = box.developer_advance(t, {new_rel: Moved(old_rel)}, finished=True)
    no_gate_refusal(box, rows, output)
    runs = [r for r in box.old_runs() if old_rel in r["files"]]
    assert runs, box.explain(rows, output)
    assert all(r["seen"][old_rel] and r["seen"][new_rel] for r in runs), (
        box.explain(rows, output) + f"\n{[r['seen'] for r in runs]}")


def test_ac8_type_changed_file_in_set(box):
    """Запись со статусом `T` (файл тестов стал символьной ссылкой) входит в C — прежняя версия гоняется.

    Сценарий: проект `junit-xml`; ветка заменяет файл тестов
    символьной ссылкой на копию его текста под `tests/data/`; мандат
    Оператора на путь. На стороне прежних версий гонялся этот путь.

    Ловит мутацию: в C берутся только статусы `M`/`D`/`R` — запись `T`
    выпала, третьей выписки нет.
    """
    rel, name = box.py_rel(), box.py_name()
    project = box.junit({rel: [name], box.py_rel(): [box.py_name()]})
    t = box.task(project)
    data = f"tests/data/{box.word()}.txt"
    grant(box, t, paths=[rel])
    rows, output = box.developer_advance(
        t, {data: py_source([name]), rel: Link(os.path.relpath(data, "tests"))},
        finished=True)
    no_gate_refusal(box, rows, output)
    assert rel in box.old_files(), box.explain(rows, output)


def test_ac9_code_only_and_new_file_no_third_checkout(box):
    """Компонент без поля `tests`: ветка правит только код либо добавляет новый файл тестов (`A`) — третьей выписки нет.

    Сценарий (подслучай — свежая задача): (а) правка только кода; (в)
    новый файл тестов `tests/test_<имя>.py` с зелёным тестом. В обоих —
    гейт пройден, среди `worktree add` гейта нет третьей выписки,
    прогонов на стороне прежних версий нет.

    Ловит мутацию: у компонента без `tests` C — все файлы отчёта базы
    (буквальное «все файлы») — третья выписка при правке кода; файлы
    `A` входят в C — третья выписка при новом файле.
    """
    for label in ("код", "новый файл"):
        case = f"{label}, зерно {box.seed}: "
        project = box.junit({box.py_rel(): [box.py_name()],
                              box.py_rel(): [box.py_name()]})
        t = box.task(project)
        changes = ({f"lib/{box.word()}.py": "VALUE = 2\n"} if label == "код"
                   else {box.py_rel(): py_source([box.py_name()])})
        rows, output = box.developer_advance(t, changes)
        no_gate_refusal(box, rows, output, case=case)
        passed(box, rows, output, case=case)
        assert box.third_adds() == [], case + box.explain(rows, output)
        assert box.old_runs() == [], case + box.explain(rows, output)


def test_ac9_changed_base_file_and_file_level_record_in_set(box):
    """Компонент без поля `tests`: изменённый файл отчёта базы — единственный файл прогона прежних версий; файл с одной лишь записью ошибки уровня файла входит в C.

    Сценарий (подслучай — свежая задача): (б) три файла тестов базы,
    ветка правит один (из `random`) — на стороне прежних версий
    гоняется только он; (г) файл базы, у которого в отчёте базы только
    запись ошибки сбора модуля, ветка исправляет — он гоняется на
    стороне прежних версий.

    Ловит мутацию: C — все файлы отчёта базы — на третьей выписке
    гоняются и неизменённые файлы; файлы записей ошибок уровня файла
    не входят в перечень отчёта базы — (г) без третьей выписки.
    """
    case = f"правка файла, зерно {box.seed}: "
    tests = {box.py_rel(): [box.py_name()] for _ in range(3)}
    rel = box.rng.choice(sorted(tests))
    project = box.junit(tests)
    t = box.task(project)
    rows, output = box.developer_advance(t, {rel: box.edited_py(tests[rel])})
    no_gate_refusal(box, rows, output, case=case)
    assert box.old_files() == {rel}, case + box.explain(rows, output)
    case = f"ошибка уровня файла, зерно {box.seed}: "
    rel, names = box.py_rel(), [box.py_name()]
    project = box.junit({box.py_rel(): [box.py_name()]},
                         files={rel: FILE_ERROR_MARK + "\n" + py_source(names)})
    t = box.task(project)
    rows, output = box.developer_advance(t, {rel: py_source(names)})
    no_gate_refusal(box, rows, output, case=case)
    assert rel in box.old_files(), case + box.explain(rows, output)


def test_ac11_third_checkout_failure_refuses_prepare(box):
    """Сбой `worktree add` третьей выписки — отказ подготовки, переход не совершён, каталога выписки нет.

    Сценарий: проект `junit-xml`, файл тестов изменён веткой; git
    отказывает `worktree add` гейта с каталогом, отличным от
    `base`/`head`. Отказ «… — подготовка», задача в `in_dev`, после
    гейта пути третьей выписки нет.

    Ловит мутацию: сбой выписки проглочен как пустой C — гейт пройден,
    задача в `verifying`.
    """
    rel, names = box.py_rel(), [box.py_name()]
    project = box.junit({rel: names})
    t = box.task(project)

    def third(args):
        path = box.add_path(args)
        return path is not None and path.name not in SIDES
    box.git_fail = third
    rows, output = box.developer_advance(t, {rel: box.edited_py(names)})
    box.git_fail = None
    refusal(box, rows, output, PREPARE_ACTION)
    assert box.third_adds(), box.explain(rows, output)
    for add in box.third_adds():
        assert not add["path"].exists(), box.explain(rows, output)


def test_ac11_third_run_failure_refuses_prepare(box):
    """Прогон на третьей выписке превысил предел — отказ подготовки, переход не совершён, выписка убрана.

    Сценарий: проект `junit-xml`, файл тестов изменён веткой; раннер на
    стороне прежних версий превышает предел времени. Отказ «… —
    подготовка», задача в `in_dev`, каталога третьей выписки после
    гейта нет.

    Ловит мутацию: таймаут прогона прежних версий считается красным
    исходом или пропуском — отказ иного действия либо проход; уборка
    третьей выписки не в `finally` — каталог остался.
    """
    rel, names = box.py_rel(), [box.py_name()]
    project = box.junit({rel: names})
    t = box.task(project)
    box.timeout_when = lambda run: run["side"] == OLD
    rows, output = box.developer_advance(t, {rel: box.edited_py(names)})
    box.timeout_when = None
    refusal(box, rows, output, PREPARE_ACTION)
    assert box.third_adds(), box.explain(rows, output)
    for add in box.third_adds():
        assert not add["path"].exists(), box.explain(rows, output)


def test_ac12_diff_failures_refuse_prepare(box):
    """Сбой `git diff --name-status` базы и головы либо `git diff -M -U0` базы и головы — отказ подготовки, переход не совершён.

    Сценарий (подслучай — свежая задача): ветка правит файл тестов и
    добавляет в файл кода строку с `NODE_ENV`; git в кадрах гейта
    отказывает (а) `diff` с `--name-status`; (б) `diff` с `-U0`. В обоих
    — отказ «… — подготовка», задача в `in_dev`.

    Ловит мутацию: `None` диффа имён — пустой C и ноль находок
    строгого режима — гейт идёт дальше; сбой `diff -U0` — ноль находок
    «исключение в коде» — отказ общего действия либо проход.
    """
    rules = {"name-status": lambda args: "diff" in args and "--name-status" in args,
             "U0": lambda args: "diff" in args and "-U0" in args}
    for label, rule in rules.items():
        case = f"{label}, зерно {box.seed}: "
        rel, names = box.py_rel(), [box.py_name()]
        project = box.junit({rel: names})
        t = box.task(project)
        box.git_fail = rule
        rows, output = box.developer_advance(
            t, {rel: box.edited_py(names),
                f"lib/{box.word()}.py": "import os\nMODE = os.environ['NODE_ENV']\n"})
        box.git_fail = None
        refusal(box, rows, output, PREPARE_ACTION, case=case)


def test_ac13_third_checkout_in_scratch_with_marker_and_removed(box):
    """Третья выписка заводится в том же `scratch`, где уже лежит маркер владельца, и убирается после гейта.

    Сценарий: проект `junit-xml`, файл тестов изменён веткой. Среди
    `worktree add` гейта есть третья выписка; в момент вызова рядом с её
    каталогом лежит `liveness.GATE_OWNER_MARKER`, её родитель — тот же
    каталог, что у выписки базы; после гейта каталога третьей выписки
    нет.

    Ловит мутацию: третья выписка — во временном каталоге вне `scratch`
    (без маркера владельца) — маркера рядом нет и родитель другой;
    выписка не попадает в `trees` и не убирается — каталог остался.
    """
    rel, names = box.py_rel(), [box.py_name()]
    project = box.junit({rel: names})
    t = box.task(project)
    rows, output = box.developer_advance(t, {rel: box.edited_py(names)})
    third = box.third_adds()
    assert len(third) == 1, box.explain(rows, output) + f"\n{box.gate_adds}"
    base = [a for a in box.gate_adds if a["path"].name == "base"]
    assert base, box.explain(rows, output)
    assert third[0]["marker"], box.explain(rows, output)
    assert third[0]["path"].parent == base[0]["path"].parent, box.explain(rows, output)
    assert not third[0]["path"].exists(), box.explain(rows, output)


def test_ac32_added_conftest_under_test_support_removed(box):
    """Добавленный `conftest.py` под маской `test_support` на третьей выписке удалён: прежняя версия изменённого теста красная — находка и отказ.

    Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
    добавляет `support/conftest.py` и правит существующий тест. На
    стороне прежних версий файла нет; отказ «… по исходам» со строкой
    «прежняя версия красная на коде ветки: <id> — …».

    Ловит мутацию: файлы `A` под `test_support` на третьей выписке
    остаются — прежняя версия «спасена», гейт пройден.
    """
    conftest_case(box, {"test_support": flow(["support/**"])}, "support/conftest.py")


def test_ac32_added_conftest_under_tests_masks_removed(box):
    """Добавленный `conftest.py` под масками `tests` компонента с полем `tests` на третьей выписке удалён — находка «прежняя версия красная на коде ветки» и отказ.

    Сценарий: проект `junit-xml` с `tests: [tests/**]`; ветка добавляет
    `tests/conftest.py` и правит существующий тест.

    Ловит мутацию: удаляются только файлы `A` с записями в отчёте —
    `conftest.py` без записей остаётся, гейт пройден.
    """
    conftest_case(box, {"tests": flow(["tests/**"])}, "tests/conftest.py")


def test_ac32_added_conftest_under_scope_without_tests_removed(box):
    """Компонент без `tests` и `test_support`: добавленный `conftest.py` под `weakening_scope` (записей в отчёте головы нет) на третьей выписке удалён — находка и отказ.

    Сценарий: проект `junit-xml` без `tests`/`test_support`
    (`weakening_scope: tests/**`); ветка добавляет `tests/conftest.py` и
    правит существующий тест.

    Ловит мутацию: у компонента без `tests` удаляются только файлы `A`
    с записями в отчёте головы (определение для поиска подстрок) —
    `conftest.py` остаётся, гейт пройден.
    """
    conftest_case(box, None, "tests/conftest.py")


def test_ac33_prior_skipped_or_missing_is_red(box):
    """Исход прежней версии «пропуск» и «нет записи» при зелёной базе — красный: трижды такой исход — находка «прежняя версия красная на коде ветки» и отказ.

    Сценарий (подслучай — свежая задача): проект `junit-xml`, файл
    теста изменён веткой; на стороне прежних версий тест (а) `skipped`
    во всех прогонах; (б) без записи во всех прогонах. Отказ «… по
    исходам» со строкой «прежняя версия красная на коде ветки: <id> — …».

    Ловит мутацию: зелёным считается всё, кроме `failed`/`error` —
    пропуск и отсутствие записи не находка, гейт пройден.
    """
    for label in ("skipped", "missing"):
        case = f"{label}, зерно {box.seed}: "
        rel, names = box.py_rel(), [box.py_name(), box.py_name()]
        project = box.junit({rel: names})
        t = box.task(project)
        box.cases[(rel, names[0])] = {"base": ["passed"], "head": ["passed"],
                                       OLD: [label]}
        rows, output = box.developer_advance(t, {rel: box.edited_py(names)})
        detail = refusal(box, rows, output, OUTCOME_ACTION, case=case)
        cid = box.case_id(project, rel, names[0])
        assert box.starting(detail, f"{PRIOR_RED}: {cid} — "), case + box.explain(rows, output)


def test_ac30_test_profile_no_outcome_gate(box):
    """У записи `test_profile` гейт исходов не создаётся и при правках, дающих находки новых видов в границе: нет ни прогона, ни записи журнала.

    Сценарий: учебный проект с `test_profile` (`report: junit-xml`);
    ветка правит файл тестов и добавляет файл кода со строкой
    `NODE_ENV`. `advance` из `in_dev`: полный набор не звался, `worktree
    add` гейта нет, ни одной записи с «по исходам»/«гейт исходов»,
    задача в `verifying`.

    Ловит мутацию: строгий режим, исключения в коде или прежние версии
    исполняются вне границы `in_outcome_bounds` — прогон, выписки и
    записи гейта у `test_profile`.
    """
    rel, names = box.py_rel(), [box.py_name()]
    project = box.junit_project({rel: names}, test_profile=True)
    t = box.task(project)
    rows, output = box.developer_advance(t, {
        rel: box.edited_py(names),
        f"lib/{box.word()}.py": "import os\nMODE = os.environ['NODE_ENV']\n"})
    assert box.suite_calls == [], box.explain(rows, output)
    assert box.gate_adds == [], box.explain(rows, output)
    assert box.gate_rows(rows) == [], box.explain(rows, output)
    assert box.state(t) == "verifying", box.explain(rows, output)
