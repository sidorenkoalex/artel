"""Файл решения `reject --decision`: номер подраздела только из цифр ASCII, форма ключа `--decision=<файл>` равносильна форме через пробел, повтор ключа и пустое значение — отказ до `fsm.cmd_reject`.

Группа: долгоживущий
Красен до реализации: `spec_gate_decision.parse` проверяет номер через `str.isdigit()` — «²» роняет `ValueError`, «３»/«١» дают «не по порядку»; `artel.py reject` не знает формы `--decision=<файл>` (уходит причиной в `fsm.cmd_reject`), пропускает `--decision ""` и не называет повтор ключа.

Разбор файла (AC-1–AC-3) — модульные тесты `spec_gate_decision.parse` без
песочницы. Разбор аргументов (AC-4–AC-7) — команда `artel.main()` тем же argv,
что набирает Оператор (`reject <id> …` доходит до закрытого `_cmd_reject`
только через неё), во временном корне `tmp_root` без признака процесса роли;
`fsm.cmd_reject` подменён, его вызов сверяется по сигнатуре настоящей
функции (`inspect.signature(...).bind`), а не по форме позиционных и
именованных аргументов. Сквозные AC-8/AC-9 держат связку «команда CLI — БД —
ссылка документов — журнал» в `ComponentsOutcomeSandbox` (настоящий git,
задача на `spec_gate`), `config.TEMPLATES` — каталог песочницы с шаблоном
файла решения.

Пути, причины, тексты решений и порядок вариантов — из `random` при каждом
запуске; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы зелёные.
"""
import contextlib
import inspect
import io
import random
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import artel, checkpoint, config, fsm, store, workspace
from orchestrator import spec_gate_decision as decision
from tests.components_outcome_sandbox import ComponentsOutcomeSandbox
from tests.fixtures import _sandbox
from tests.outcome_gate_sandbox import spec_text, ulid

SEED = random.randrange(2 ** 32)
print(f"зерно: {SEED}")

HEADER = "# Решение Оператора на гейте SPEC"
PREFIX = "возврат из spec_gate: "
RETURN_ACTION = "state -> spec_writing"
TEMPLATE_NAME = "SPEC-GATE-DECISION.md"
NOT_INTEGER = "не целое"
OUT_OF_ORDER = "не по порядку"
NO_VALUE = "без значения"
NOT_COMBINED = "не сочетается с позиционной причиной"
REPEATED = "ключ --decision повторён"

FIELDS = ("Текст", "Утверждения о коде и поведении", "Чем проверяется",
          "Существующие тесты", "Прежние решения", "Зоны")

TEMPLATE_TEXT = """# Решение Оператора на гейте SPEC

<!-- Файл для `artel.py reject <id> --decision <файл>`. Каждое решение — подраздел «### Решение <n>» с пятью полями; пустое поле — отказ команды. -->

## Решения

### Решение 1
Текст: <что решено — одной-тремя фразами>
Утверждения о коде и поведении: <`файл:строка`; или «опыт: <что сделано и что увидено>»; или «нет»>
Чем проверяется: <критерий AC-n и тест; против чего — «временный дублёр» или «не меняет файлов»>
Существующие тесты: <тесты, вызывающие изменяемые функции, с решением «не ломаются»; или «мандат: <строка мандата>»; или «нет»>
Прежние решения: <номера k.n, с которыми сверено, и «противоречий нет»; или «первое решение»>
Зоны: <«выполнимо в зонах SPEC» или пути для расширения>
"""

LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Сигнатура настоящей `fsm.cmd_reject` — до любой подмены.
REJECT_SIGNATURE = inspect.signature(fsm.cmd_reject)


def why(text: str) -> str:
    return f"зерно: {SEED}\n{text}"


def word(rng: random.Random, size: int = 6) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(size))


# ------------------------------------------------------------ файл решения


def good_fields(rng: random.Random) -> dict:
    """Поля одного решения по форме шаблона (варианты значений — от зерна)."""
    return {
        "Текст": f"решено {word(rng)} {word(rng)}",
        "Утверждения о коде и поведении": rng.choice((
            "нет", "`orchestrator/fsm.py:1863`",
            f"опыт: прогнал {word(rng)} и увидел отказ")),
        "Чем проверяется": (f"AC-{rng.randint(1, 9)} тестом test_{word(rng)}; "
                            + rng.choice(("временный дублёр",
                                          "не меняет файлов"))),
        "Существующие тесты": rng.choice((
            "нет", "tests/test_fsm_spec_gate_reject.py не ломаются")),
        "Прежние решения": "первое решение",
        "Зоны": rng.choice(("выполнимо в зонах SPEC", "orchestrator/fsm.py")),
    }


def render(decisions, numbers) -> str:
    """Текст файла решения: подразделы «### Решение <numbers[i]>» с полями `decisions[i]`."""
    lines = [HEADER, "", "## Решения", ""]
    for number, fields in zip(numbers, decisions):
        lines.append(f"### Решение {number}")
        lines += [f"{name}: {fields[name]}" for name in FIELDS]
        lines.append("")
    return "\n".join(lines)


def file_with_numbers(rng: random.Random, numbers) -> str:
    return render([good_fields(rng) for _ in numbers], numbers)


# ---------------------------------------------------------------- AC-1


@pytest.mark.parametrize("numbers", [["²"], ["1", "²"], ["¹"], ["1", "2", "³"]])
def test_ac1_superscript_number_is_decision_error(numbers):
    """Подраздел «### Решение ²» (и прочие надстрочные цифры) — `DecisionError` «не целое», не `ValueError`.

    Сценарий: файл решения по форме, номер одного из подразделов —
    надстрочная цифра Юникода (`str.isdigit()` для неё истинно, `int()`
    падает), стоящая первой или после верных номеров. `parse` поднимает
    `DecisionError`, текст которого содержит «не целое».

    Ловит мутацию: возврат к проверке номера `str.isdigit()` — «²» проходит
    проверку, `int("²")` поднимает `ValueError`, и вместо `DecisionError`
    тест получает трассировку `ValueError`.
    """
    rng = random.Random(SEED)
    text = file_with_numbers(rng, numbers)

    with pytest.raises(decision.DecisionError) as caught:
        decision.parse(text)

    assert NOT_INTEGER in str(caught.value), why(f"текст отказа: {caught.value}")


# ---------------------------------------------------------------- AC-2


@pytest.mark.parametrize("numbers", [
    ["３"], ["1", "2", "３"], ["١"], ["1", "٢"], ["1", "２"],
])
def test_ac2_non_ascii_digits_are_not_integer(numbers):
    """Полноширинные и арабско-индийские цифры номера — `DecisionError` «не целое», не «не по порядку».

    Сценарий: файл решения по форме, номер подраздела — цифра Юникода вне
    ASCII, которую `int()` принимает; она стоит и не на своём месте («３»
    первым), и на своём («３» третьим, «١» первым, «٢» вторым) — значение
    `int()` совпадает с ожидаемым порядковым номером. `parse` поднимает
    `DecisionError` с «не целое» и без «не по порядку».

    Ловит мутацию: номер проверяется `str.isdigit()`/`str.isdecimal()` вместо
    цифр ASCII — «３» и «١» проходят проверку числа, и отказ звучит «не по
    порядку» вместо «не целое».
    """
    rng = random.Random(SEED)
    text = file_with_numbers(rng, numbers)

    with pytest.raises(decision.DecisionError) as caught:
        decision.parse(text)

    message = str(caught.value)
    assert NOT_INTEGER in message, why(f"текст отказа: {message}")
    assert OUT_OF_ORDER not in message, why(f"текст отказа: {message}")


# ---------------------------------------------------------------- AC-3


def test_ac3_ascii_numbers_parsed_as_before():
    """Подразделы «### Решение 1» … «### Решение 3» разбираются в номера 1, 2, 3 с их полями.

    Сценарий: файл из трёх решений по форме, значения полей — от зерна.
    `parse` возвращает три решения по порядку: номер — целое 1, 2, 3, поля —
    значения из файла.

    Ловит мутацию: условие новой проверки ASCII перевёрнуто (`if
    number.isascii()` вместо `if not …`) — `parse` поднимает `DecisionError`
    на верном файле; либо номер возвращается строкой «1» вместо целого —
    `number` не равен 1, 2, 3.
    """
    rng = random.Random(SEED)
    decisions = [good_fields(rng) for _ in range(3)]

    parsed = decision.parse(render(decisions, ["1", "2", "3"]))

    assert [item["number"] for item in parsed] == [1, 2, 3], why(str(parsed))
    for item, fields in zip(parsed, decisions):
        for name in FIELDS:
            assert item["fields"][name] == fields[name], why(
                f"решение {item['number']}, поле «{name}»: {item['fields']}")


# ------------------------------------------------------- разбор аргументов


def run_reject(*argv: str) -> SimpleNamespace:
    """`artel.py reject <argv>` с подменённой `fsm.cmd_reject`: (подмена, текст отказа или `None`, вывод)."""
    out = io.StringIO()
    refusal = None
    with mock.patch.object(fsm, "cmd_reject") as fake, \
            mock.patch.object(sys, "argv", ["artel.py", "reject", *argv]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            artel.main()
        except SystemExit as exc:
            if exc.code not in (0, None):
                refusal = str(exc.code)
    return SimpleNamespace(fake=fake, refusal=refusal, out=out.getvalue())


def reject_arguments(result) -> dict:
    """Аргументы единственного вызова `fsm.cmd_reject` по именам её сигнатуры."""
    assert result.fake.call_count == 1, why(
        f"вызовов fsm.cmd_reject: {result.fake.call_count}; отказ: "
        f"{result.refusal}; вывод: {result.out}")
    call = result.fake.call_args
    bound = REJECT_SIGNATURE.bind(*call.args, **call.kwargs)
    bound.apply_defaults()
    return {name: bound.arguments[name]
            for name in ("task_id", "reason", "decision_file")}


def assert_refused(result, fragment: str | None, argv) -> None:
    """Отказ команды: ненулевой выход, `fsm.cmd_reject` не вызван, текст содержит `fragment`."""
    text = f"argv: {list(argv)}\nотказ: {result.refusal}\nвывод: {result.out}"
    assert result.refusal is not None, why(f"отказа нет\n{text}")
    assert not result.fake.called, why(f"fsm.cmd_reject вызван\n{text}")
    if fragment is not None:
        assert fragment in result.refusal, why(f"нет «{fragment}»\n{text}")


def sample_path(rng: random.Random, tmp_root) -> str:
    return rng.choice((f"{word(rng)}.md", str(tmp_root.root / f"{word(rng)}.md"),
                       f"reshenie/{word(rng)}-{rng.randint(1, 99)}.md"))


# ---------------------------------------------------------------- AC-4


def test_ac4_equals_form_calls_reject_like_space_form(tmp_root):
    """`--decision=<путь>` зовёт `fsm.cmd_reject` с файлом решения и пустой причиной — как `--decision <путь>`; значение — по первому «=».

    Сценарий: для нескольких путей (относительных, абсолютных, со знаком
    «=») команда `reject <id> --decision=<путь>` и `reject <id> --decision
    <путь>`; аргументы вызова подменённой `fsm.cmd_reject` совпадают:
    `decision_file` — путь целиком, `reason` — пустая строка. Отдельно
    `--decision=a=b.md` — файл `a=b.md`.

    Ловит мутацию: форма с «=» не распознаётся ключом — `fsm.cmd_reject`
    получает причину «--decision=<путь>» без `decision_file`; либо значение
    режется по последнему «=» — для `a=b.md` файлом становится `b.md`.
    """
    rng = random.Random(SEED)
    paths = [sample_path(rng, tmp_root) for _ in range(3)]
    paths += ["a=b.md", f"{word(rng)}={word(rng)}.md"]
    for path in paths:
        tid = ulid(rng)
        expected = {"task_id": tid, "reason": "", "decision_file": path}

        equals = reject_arguments(run_reject(tid, f"--decision={path}"))
        space = reject_arguments(run_reject(tid, "--decision", path))

        assert equals == expected, why(f"путь {path!r}: {equals}")
        assert space == expected, why(f"путь {path!r}: {space}")


# ---------------------------------------------------------------- AC-5


@pytest.mark.parametrize("value", [["--decision="], ["--decision=--x"],
                                   ["--decision", ""]])
def test_ac5_empty_or_dashed_value_refused_without_reject(tmp_root, value):
    """Пустое значение и значение с «--» в форме с «=», пустой аргумент через пробел — отказ «без значения», `fsm.cmd_reject` не вызван.

    Сценарий: `reject <id> --decision=`, `reject <id> --decision=--x`,
    `reject <id> --decision ""`; каждая команда завершается отказом с
    «без значения», подменённая `fsm.cmd_reject` не вызвана.

    Ловит мутацию: проверка значения формы через пробел осталась
    `args[at + 1].startswith("--")` — пустая строка проходит, и
    `fsm.cmd_reject` зовётся с `decision_file=""`; либо форма с «=» берёт
    пустой остаток файлом без проверки.
    """
    rng = random.Random(SEED)
    argv = [ulid(rng), *value]

    assert_refused(run_reject(*argv), NO_VALUE, argv)


# ---------------------------------------------------------------- AC-6


def test_ac6_combination_repeat_and_check_order_refused(tmp_root):
    """Ключ с «=» вместе с причиной — «не сочетается», два ключа в любой форме — «повторён»; повтор проверяется раньше пустого значения, пустое — раньше причины.

    Сценарий (порядок вариантов — от зерна): `--decision=<путь>` до и после
    позиционной причины — отказ с «не сочетается с позиционной причиной»;
    пять сочетаний двух ключей из критерия — отказ с «ключ --decision
    повторён»; `--decision= причина` — отказ с «без значения» и без «не
    сочетается»; `--decision=<a> --decision= причина` — отказ с «ключ
    --decision повторён». Во всех случаях подменённая `fsm.cmd_reject` не
    вызвана.

    Ловит мутацию: учитывается только первый ключ — второй уходит в
    позиционный остаток, и отказ звучит «не сочетается» вместо «повторён»;
    либо позиционная причина проверяется раньше значения — `--decision=
    причина` даёт «не сочетается».
    """
    rng = random.Random(SEED)
    tid = ulid(rng)
    a, b = f"{word(rng)}.md", f"{word(rng)}.md"
    reason = f"причина {word(rng)} {word(rng)}"
    cases = [
        ([tid, f"--decision={a}", reason], NOT_COMBINED),
        ([tid, reason, f"--decision={a}"], NOT_COMBINED),
        ([tid, "--decision", a, "--decision", b], REPEATED),
        ([tid, f"--decision={a}", "--decision", b], REPEATED),
        ([tid, "--decision", a, f"--decision={b}"], REPEATED),
        ([tid, f"--decision={a}", f"--decision={b}"], REPEATED),
        ([tid, "--decision", f"--decision={b}"], REPEATED),
        ([tid, "--decision=", reason], NO_VALUE),
        ([tid, f"--decision={a}", "--decision=", reason], REPEATED),
    ]
    rng.shuffle(cases)
    for argv, fragment in cases:
        result = run_reject(*argv)

        assert_refused(result, fragment, argv)
        if fragment == NO_VALUE:
            assert "не сочетается" not in result.refusal, why(
                f"argv: {argv}\nотказ: {result.refusal}")


# ---------------------------------------------------------------- AC-7


def test_ac7_previous_forms_unchanged(tmp_root):
    """Позиционная причина, `--decision <файл>`, прежние отказы и `--decisions` ведут себя как до задачи.

    Сценарий: `reject <id> <причина>` зовёт `fsm.cmd_reject` с этой причиной
    и без файла решения; `reject <id> --decision <путь>` — с файлом и пустой
    причиной; `--decision` без значения и с `--x` — отказ «без значения»;
    `--decision <путь>` до и после причины — отказ «не сочетается с
    позиционной причиной»; два ключа через пробел — отказ (текст — по AC-6);
    `reject <id> --decisions` зовёт `fsm.cmd_reject` с причиной
    «--decisions».

    Ловит мутацию: ключом считается любой аргумент с началом `--decision`
    (`startswith` без «=») — `--decisions` даёт отказ или файл решения
    «s» вместо причины «--decisions»; либо позиционная причина теряется
    (`fsm.cmd_reject` получает пустую причину).
    """
    rng = random.Random(SEED)
    tid = ulid(rng)
    reason = f"причина {word(rng)} {word(rng)}"
    path = sample_path(rng, tmp_root)

    assert reject_arguments(run_reject(tid, reason)) == {
        "task_id": tid, "reason": reason, "decision_file": None}
    assert reject_arguments(run_reject(tid, "--decision", path)) == {
        "task_id": tid, "reason": "", "decision_file": path}
    assert reject_arguments(run_reject(tid, "--decisions")) == {
        "task_id": tid, "reason": "--decisions", "decision_file": None}
    refused = [
        ([tid, "--decision"], NO_VALUE),
        ([tid, "--decision", "--x"], NO_VALUE),
        ([tid, "--decision", path, reason], NOT_COMBINED),
        ([tid, reason, "--decision", path], NOT_COMBINED),
        ([tid, "--decision", path, "--decision", f"{word(rng)}.md"], None),
    ]
    for argv, fragment in refused:
        assert_refused(run_reject(*argv), fragment, argv)


# ------------------------------------------------------ сквозные AC-8/AC-9


@pytest.fixture
def box():
    """Стенд ComponentsOutcomeSandbox после setUp; `config.TEMPLATES` — каталог песочницы с шаблоном файла решения."""
    for obj in _sandbox(ComponentsOutcomeSandbox):
        templates = obj.root / ".artel" / f"templates-{obj.word()}"
        templates.mkdir(parents=True)
        (templates / TEMPLATE_NAME).write_text(TEMPLATE_TEXT, encoding="utf-8")
        with mock.patch.object(config, "TEMPLATES", templates):
            yield obj


def new_task(box) -> SimpleNamespace:
    """Задача учебного проекта на `spec_gate`: рабочая копия, SPEC.md в ссылке документов, вход на гейт — записью журнала."""
    project = getattr(box, "decision_project", None)
    if project is None:
        project = box.decision_project = box.training()
    tid = ulid(box.rng)
    branch = f"task/{tid.lower()}-{box.word()}"
    store.insert_task(box.conn, tid, f"Гейт SPEC {box.word()}", "spec_writing",
                      branch, project.name, 25.0)
    store.update_task(box.conn, tid, zones=box.zones_of("frontend"))
    _wt, error = workspace.ensure(tid, branch)
    assert error is None, box.note(f"рабочая копия не заведена: {error}")
    docs = config.PROJECTS / project.name / "tasks" / tid
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "SPEC.md").write_text(spec_text(tid, (1,)), encoding="utf-8")
    checkpoint.commit_step_artifacts(box.conn, tid, "analyst")
    store.set_state(box.conn, tid, "spec_gate", "analyst",
                    expected_state="spec_writing", detail="SPEC готов")
    return SimpleNamespace(id=tid)


def cli(box, *argv: str) -> tuple[bool, str]:
    """(успех, stdout + stderr + текст отказа) команды `artel.py <argv>`."""
    out = io.StringIO()
    ok = True
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            artel.main()
        except SystemExit as exc:
            if exc.code not in (0, None):
                ok = False
                out.write(f"\n{exc.code}")
    return ok, out.getvalue()


def write_file(box, text: str) -> str:
    """Абсолютный путь файла решения с текстом `text` во временном корне песочницы."""
    path = box.root / ".artel" / f"reshenie-{box.word()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def state(box, t) -> str:
    return store.get_task(box.conn, t.id)["state"]


def returns(box, t) -> list[tuple]:
    """(исполнитель, текст) записей возврата `state -> spec_writing` журнала задачи по порядку."""
    return [(row["actor"], row["detail"] or "")
            for row in store.task_steps(box.conn, t.id)
            if row["action"] == RETURN_ACTION]


# ---------------------------------------------------------------- AC-8


def test_ac8_equals_form_end_to_end_same_as_space_form(box):
    """`reject <id> --decision=<абсолютный путь>` на `spec_gate` даёт тот же переход и ту же запись возврата, что форма через пробел, без предупреждения о тексте.

    Сценарий: две задачи на `spec_gate`, файл решения по форме шаблона
    (1–3 решения, значения — от зерна) по абсолютному пути; одной задаче —
    `reject <id> --decision=<путь>`, другой — `reject <id> --decision
    <путь>` (порядок — от зерна). Обе команды успешны, обе задачи в
    `spec_writing`, у каждой ровно одна новая запись возврата; исполнитель
    и текст записи у обеих форм совпадают и равны «возврат из spec_gate: »
    плюс текст файла; в выводе формы с «=» нет `fsm.SPEC_GATE_TEXT_WARNING`.

    Ловит мутацию: форма с «=» уходит в `fsm.cmd_reject` позиционной
    причиной — запись возврата несёт «--decision=<путь>» вместо текста
    файла, а вывод — предупреждение `SPEC_GATE_TEXT_WARNING`.
    """
    count = box.rng.randint(1, 3)
    text = render([good_fields(box.rng) for _ in range(count)],
                  [str(n) for n in range(1, count + 1)])
    forms = ["equals", "space"]
    box.rng.shuffle(forms)
    records = {}
    for form in forms:
        t = new_task(box)
        path = write_file(box, text)
        argv = ([f"--decision={path}"] if form == "equals"
                else ["--decision", path])

        ok, out = cli(box, "reject", t.id, *argv)

        note = box.note(f"форма {form}, вывод:\n{out}\nжурнал: {returns(box, t)}")
        assert ok, note
        assert state(box, t) == "spec_writing", note
        assert len(returns(box, t)) == 1, note
        assert fsm.SPEC_GATE_TEXT_WARNING not in out, note
        records[form] = returns(box, t)[-1]
    assert records["equals"] == records["space"], box.note(str(records))
    assert records["equals"][1].rstrip() == (PREFIX + text).rstrip(), box.note(
        str(records))


# ---------------------------------------------------------------- AC-9


def test_ac9_superscript_number_refused_end_to_end(box):
    """`reject <id> --decision <файл>` с «### Решение ²» — отказ файла решения без трассировки, задача на `spec_gate`, журнал возврата прежний.

    Сценарий: задача на `spec_gate`; файл решения по форме, номер
    подраздела «²» первым либо после «1» (вариант — от зерна). Команда
    завершается ненулевым выходом, задача остаётся на `spec_gate`, число
    записей возврата `state -> spec_writing` не изменилось, в выводе нет
    `Traceback`.

    Ловит мутацию: возврат к проверке номера `str.isdigit()` — `int("²")`
    пробрасывает `ValueError` сквозь `artel.main()` вместо отказа файла
    решения, и команда падает трассировкой.
    """
    t = new_task(box)
    numbers = box.rng.choice((["²"], ["1", "²"]))
    before = len(returns(box, t))

    ok, out = cli(box, "reject", t.id, "--decision",
                  write_file(box, file_with_numbers(box.rng, numbers)))

    note = box.note(f"номера {numbers}, вывод:\n{out}")
    assert not ok, note
    assert state(box, t) == "spec_gate", note
    assert len(returns(box, t)) == before, note
    assert "Traceback" not in out, note
