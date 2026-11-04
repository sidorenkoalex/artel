"""Возврат с гейта SPEC файлом решения: `reject <id> --decision <файл>` — форма файла, заглушки шаблона, номера прежних решений, мандат тестов, перечень прежних решений, прежняя форма с предупреждением, отказы команды.

Группа: долгоживущий
Красен до реализации: ключа `--decision` пульт не знает — `artel.py reject <id> --decision <файл>` берёт «--decision» текстом причины и возвращает задачу в `spec_writing` (отказов формы, номеров, мандата нет, журнал пополняется), модуля `orchestrator/spec_gate_decision.py` нет, прежняя форма не печатает предупреждения и принимает причину с заголовком файла решения, подсказка `auto` и справка не называют `--decision`.

Песочница — `tests.components_outcome_sandbox.ComponentsOutcomeSandbox`
(настоящий git, клон артели с `origin`, учебный внешний проект из двух
компонентов `backend`/`frontend`): связка «команда CLI `artel.main()` — БД —
ссылка документов — журнал». Задача заводится строкой БД на `spec_gate` с
зонами компонента `frontend`, рабочей копией (`workspace.ensure`) и SPEC.md в
ссылке документов (автокоммит шага аналитика). Команды Оператора — через
`artel.main()` тем же argv, что набирает Оператор; `answer` — настоящий
коммит ANSWER-n; подсказка остановки — `auto.cmd_auto`; брифы —
`brief.analyst_map_component`/`brief.spec_auditor_brief`. Возврат задачи на
гейт после принятого возврата — `store.set_state` (`spec_writing ->
spec_gate`), как его делает переход аналитика.

`config.TEMPLATES` подменён каталогом песочницы с файлом шаблона, текст
которого — дословно дифф ТЗ задачи (`TEMPLATE_TEXT`); настоящий
`templates/` пульта тесты не читают. Тексты заглушек — из него же.

Наблюдается: код выхода команды и её вывод (stdout, stderr, текст отказа),
состояние задачи, число записей возврата `state -> spec_writing` в журнале и
их текст. Имена, тексты решений, порядок полей и прежних возвратов — из
`random` при каждом запуске; зерно печатается и входит в текст каждого
провала.

Варианты отказа, не меняющего состояние, перебираются циклом по одной
задаче: песочница с git стоит секунды, отдельная на вариант утроила бы
прогон файла.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы зелёные; мутант «`mandate.elements` вместо `mandate.id_elements`» в
сверке мандата красит `test_ac7_id_mandate_prefix_before_comma_refused`.
"""
import ast
import contextlib
import importlib.util
import io
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (artel, auto, brief, checkpoint, config,
                          project_profile, store, workspace)
from orchestrator.advance_gates import mandate
from tests.components_outcome_sandbox import ComponentsOutcomeSandbox
from tests.fixtures import _sandbox
from tests.outcome_gate_sandbox import MATRIX_HEADERS, spec_text, ulid

PREFIX = "возврат из spec_gate: "
HEADER = "# Решение Оператора на гейте SPEC"
WARNING = ("решение без сверки следствий — для сессии Оператора обязательна "
           "форма --decision")
HEADER_REFUSAL = "файл решения подаётся ключом --decision"
STATE_REFUSAL = "--decision применим только на spec_gate"
ONLY_TESTS = "на spec_gate — только мандат тестов"
RETURN_ACTION = "state -> spec_writing"
TEMPLATE_NAME = "SPEC-GATE-DECISION.md"
MODULE = "orchestrator.spec_gate_decision"

FIELDS = ("Текст", "Утверждения о коде и поведении", "Чем проверяется",
          "Существующие тесты", "Прежние решения", "Зоны")

# Дословно дифф ТЗ задачи: новый файл шаблона (в ветке до мержа его нет).
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

TEMPLATE_COMMENT = next(line for line in TEMPLATE_TEXT.splitlines()
                        if line.startswith("<!--"))

# Заглушка поля — текст строки поля шаблона после «<Поле>: » целиком.
STUBS = {name: line[len(name) + 2:] for line in TEMPLATE_TEXT.splitlines()
         for name in FIELDS if line.startswith(f"{name}: <")}


@pytest.fixture
def box():
    """Стенд ComponentsOutcomeSandbox после setUp; `config.TEMPLATES` — каталог песочницы с шаблоном из ТЗ."""
    for obj in _sandbox(ComponentsOutcomeSandbox):
        templates = obj.root / ".artel" / f"templates-{obj.word()}"
        templates.mkdir(parents=True)
        (templates / TEMPLATE_NAME).write_text(TEMPLATE_TEXT, encoding="utf-8")
        obj.templates = templates
        with mock.patch.object(config, "TEMPLATES", templates):
            yield obj


# ------------------------------------------------------------- обвязка


def new_task(box, state: str = "spec_gate") -> SimpleNamespace:
    """Задача учебного проекта на компонент `frontend` в `state`: рабочая копия, SPEC.md в ссылке документов, вход на гейт — записью журнала."""
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
    # Вход на гейт записью журнала `state -> spec_gate`, как переход
    # аналитика: возврат с гейта узнаётся по предшествующему состоянию.
    store.set_state(box.conn, tid, "spec_gate", "analyst",
                    expected_state="spec_writing", detail="SPEC готов")
    if state != "spec_gate":
        store.update_task(box.conn, tid, state=state)
    return SimpleNamespace(id=tid, project=project)


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
    path = box.root / ".artel" / f"reshenie-{box.word()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def reject_decision(box, t, text: str) -> tuple[bool, str]:
    """`reject --decision` с файлом текста `text`; текст запоминается для сверки записи возврата."""
    box.last_text = text
    return cli(box, "reject", t.id, "--decision", write_file(box, text))


def state(box, t) -> str:
    return store.get_task(box.conn, t.id)["state"]


def returns(box, t) -> list[str]:
    """Тексты записей возврата `state -> spec_writing` журнала задачи по порядку."""
    return [row["detail"] or "" for row in store.task_steps(box.conn, t.id)
            if row["action"] == RETURN_ACTION]


def back_to_gate(box, t) -> None:
    store.set_state(box.conn, t.id, "spec_gate", "analyst",
                    expected_state="spec_writing",
                    detail=f"SPEC переписан {box.word()}")


def assert_refused(box, t, ok: bool, out: str, before: int, *names: str) -> None:
    """Отказ: ненулевой выход, задача на `spec_gate`, журнал возврата прежний, вывод называет `names`."""
    why = box.note(f"вывод:\n{out}")
    assert not ok, why
    assert state(box, t) == "spec_gate", why
    assert len(returns(box, t)) == before, why
    for name in names:
        assert name in out, box.note(f"нет «{name}» в выводе:\n{out}")


def assert_accepted(box, t, ok: bool, out: str, before: int,
                    text: str | None = None) -> None:
    """Принят: задача в `spec_writing`, новая запись возврата — префикс и `text` (по умолчанию — текст последнего файла решения)."""
    text = box.last_text if text is None else text
    why = box.note(f"вывод:\n{out}\nжурнал возврата:\n{returns(box, t)}")
    assert ok, why
    assert state(box, t) == "spec_writing", why
    assert len(returns(box, t)) == before + 1, why
    assert returns(box, t)[-1].rstrip() == (PREFIX + text).rstrip(), why


# --------------------------------------------------------- файл решения


def prior_value(numbers) -> str:
    """Поле «Прежние решения» по форме: ссылки «№» на все номера и «противоречий нет»; без прежних — «первое решение»."""
    if not numbers:
        return "первое решение"
    return f"сверено с {', '.join('№' + n for n in numbers)}: противоречий нет"


def good_fields(box, numbers=()) -> dict:
    """Поля одного решения по форме требования 2 (варианты значений — от зерна)."""
    rng = box.rng
    return {
        "Текст": f"решено {box.word()} {box.word()}",
        "Утверждения о коде и поведении": rng.choice((
            "нет", "`orchestrator/fsm.py:1863`", "orchestrator/fsm.py:1863–1865",
            f"опыт: прогнал {box.word()} и увидел отказ")),
        "Чем проверяется": (f"AC-{rng.randint(1, 15)} тестом test_{box.word()}; "
                            + rng.choice(("временный дублёр", "не меняет файлов"))),
        "Существующие тесты": rng.choice((
            "нет", "tests/test_fsm_spec_gate_reject.py не ломаются")),
        "Прежние решения": prior_value(numbers),
        "Зоны": rng.choice(("выполнимо в зонах SPEC", "orchestrator/fsm.py")),
    }


def render(decisions, *, numbers=None, header: str = HEADER,
           section: bool = True, order=None, lead: str = "",
           comment: bool = False) -> str:
    """Текст файла решения. Значение поля `None` — поле опущено, список — поле повторено каждым значением."""
    lines = [lead + header, ""]
    if comment:
        lines += [TEMPLATE_COMMENT, ""]
    if section:
        lines += ["## Решения", ""]
    for i, fields in enumerate(decisions):
        lines.append(f"### Решение {numbers[i] if numbers else i + 1}")
        for name in (order or FIELDS):
            value = fields.get(name)
            if value is None:
                continue
            for item in (value if isinstance(value, list) else [value]):
                lines.append(f"{name}:" + (f" {item}" if item else ""))
        lines.append("")
    return "\n".join(lines)


def text_return(box, t, reason: str) -> None:
    ok, out = cli(box, "reject", t.id, reason)
    assert ok and state(box, t) == "spec_writing", box.note(
        f"прежний возврат текстом не принят:\n{out}")
    back_to_gate(box, t)


def file_return(box, t, decisions) -> None:
    ok, out = reject_decision(box, t, render(decisions))
    assert ok and state(box, t) == "spec_writing", box.note(
        f"прежний возврат файлом не принят:\n{out}")
    back_to_gate(box, t)


def seed_returns(box, t, kinds) -> tuple[list, dict]:
    """Прежние возвраты задачи видов `kinds` («text»/«file») по порядку: (номера прежних решений, номера возвратов файлом -> число решений)."""
    numbers: list = []
    files: dict = {}
    for k, kind in enumerate(kinds, 1):
        if kind == "text":
            text_return(box, t, f"причина {box.word()} {box.word()}")
            numbers.append(str(k))
        else:
            m = box.rng.randint(2, 3)
            file_return(box, t, [good_fields(box, numbers) for _ in range(m)])
            numbers += [f"{k}.{n}" for n in range(1, m + 1)]
            files[k] = m
    return numbers, files


def has_number(line: str, number: str) -> bool:
    """Номер `number` («k» или «k.n») стоит в строке отдельным токеном."""
    return re.search(rf"(?<![\w.]){re.escape(number)}(?![\w]|\.\d)", line) is not None


def line_with(out: str, fragment: str) -> str:
    return next((line for line in out.splitlines() if fragment in line), "")


# ---------------------------------------------------------------- AC-1


def test_ac1_accepted_decision_returns_task_with_full_text(box):
    """Верно заполненный файл решения переводит задачу в `spec_writing`, текст целиком — в журнале и в брифах аналитика и аудитора.

    Сценарий: задача на `spec_gate` без прежних возвратов; файл из 1–3
    решений по форме (значения полей — от зерна). `reject --decision`
    принят: задача в `spec_writing`, последняя запись возврата — «возврат
    из spec_gate: » и текст файла целиком; бриф аналитика несёт этот текст
    после заголовка «## Причина возврата», бриф аудитора — после «##
    Решения Оператора на гейте SPEC».

    Ловит мутацию: в журнал уходит не текст файла, а путь к нему или
    сводка решений — запись возврата не совпадает с текстом файла, и в
    брифах аналитика и аудитора текста решения нет.
    """
    t = new_task(box)
    text = render([good_fields(box) for _ in range(box.rng.randint(1, 3))])

    ok, out = reject_decision(box, t, text)

    assert_accepted(box, t, ok, out, 0)
    assert returns(box, t)[-1].rstrip() == (PREFIX + text).rstrip(), box.note(
        f"запись возврата:\n{returns(box, t)[-1]}")
    analyst = brief.analyst_map_component(box.conn, t.id)
    at = analyst.find(f"## {brief.RETURN_REASON_HEADER}")
    assert at != -1, box.note(f"нет раздела «Причина возврата»:\n{analyst[:3000]}")
    assert (PREFIX + text).rstrip() in analyst[at:], box.note(analyst[:4000])
    auditor = brief.spec_auditor_brief(box.conn, t.id)
    at = auditor.find(f"## {brief.SPEC_GATE_DECISIONS_HEADER}")
    assert at != -1, box.note(f"нет раздела решений:\n{auditor[-3000:]}")
    assert text.strip() in auditor[at:], box.note(auditor[-4000:])


# ---------------------------------------------------------------- AC-2


def test_ac2_header_section_and_numbering_refused(box):
    """Файл без раздела «## Решения», без заголовка первой непустой строкой или с номерами подразделов не по порядку — отказ, задача на `spec_gate`, журнал возврата не пополнен.

    Сценарий: файл из двух решений по форме, испорченный по каждому
    случаю (порядок случаев — от зерна): нет раздела; первая строка —
    сразу «## Решения»; перед заголовком строка пояснения; заголовок без
    «SPEC»; номера «1, два», «1, 1», «1, 3», «2, 3». Отказ состояния не
    меняет, поэтому все случаи идут по одной задаче (песочница с git
    дорога, отдельная на случай удвоила бы прогон).

    Ловит мутацию: заголовок ищется в любом месте файла (`HEADER in
    text`) — файл с пояснением до заголовка проходит; номера подразделов
    только разбираются, а не сверяются «подряд с 1» — «1, 3» и «2, 3»
    проходят, задача уходит в `spec_writing`.
    """
    t = new_task(box)
    decisions = [good_fields(box), good_fields(box)]
    cases = [
        ("no_section", render(decisions, section=False)),
        ("no_header", render(decisions).split("\n", 2)[2]),
        ("other_first_line", render(decisions, lead=f"Пояснение {box.word()}\n")),
        ("short_header", render(decisions, header="# Решение Оператора на гейте")),
        ("number_not_int", render(decisions, numbers=["1", "два"])),
        ("number_repeated", render(decisions, numbers=["1", "1"])),
        ("number_gap", render(decisions, numbers=["1", "3"])),
        ("number_not_from_one", render(decisions, numbers=["2", "3"])),
    ]
    box.rng.shuffle(cases)
    for case, text in cases:
        ok, out = reject_decision(box, t, text)

        assert_refused(box, t, ok, f"[{case}]\n{out}", 0)


def test_ac2_blank_lines_and_spaces_before_header_pass(box):
    """Пустые строки и пробелы вокруг заголовка не мешают: первая непустая строка после снятия пробелов — заголовок, файл принят.

    Ловит мутацию: заголовок проверяется `text.startswith(HEADER)` без
    пропуска пустых строк и снятия пробелов — файл с пустыми строками до
    заголовка получает отказ «нет заголовка».
    """
    t = new_task(box)
    lead = "\n" * box.rng.randint(1, 3) + " " * box.rng.randint(1, 4)
    text = render([good_fields(box)], lead=lead).replace(
        HEADER, HEADER + " " * box.rng.randint(1, 3), 1)

    ok, out = reject_decision(box, t, text)

    assert_accepted(box, t, ok, out, 0)


# ---------------------------------------------------------------- AC-3


@pytest.mark.parametrize("field", ["Текст", "Утверждения о коде и поведении",
                                   "Чем проверяется", "Существующие тесты",
                                   "Прежние решения", "Зоны"])
def test_ac3_empty_missing_or_repeated_field_refused(box, field):
    """У одного решения поле пусто, опущено или повторено — отказ с именем решения и поля, задача на `spec_gate`.

    Сценарий: для поля `field` — три файла из 2–3 решений по форме; у
    решения со случайным номером поле пусто, опущено или повторено
    (второе значение тоже по форме). Отказ состояния не меняет — три
    случая идут по одной задаче.

    Ловит мутацию: повтор поля молча перезаписывает значение (словарь
    без проверки ключа) — файл с повтором проходит; отказ называет
    первое решение вместо испорченного — нет «Решение <n>» в выводе.
    """
    t = new_task(box)
    for kind in ("empty", "missing", "repeated"):
        decisions = [good_fields(box) for _ in range(box.rng.randint(2, 3))]
        n = box.rng.randrange(len(decisions))
        broken = decisions[n]
        if kind == "empty":
            broken[field] = ""
        elif kind == "missing":
            broken[field] = None
        else:
            broken[field] = [broken[field], good_fields(box)[field]]

        ok, out = reject_decision(box, t, render(decisions))

        assert_refused(box, t, ok, f"[{kind}]\n{out}", 0, f"Решение {n + 1}", field)


def test_ac3_free_order_multiline_and_mid_line_label_pass(box):
    """Поля в ином порядке, многострочные значения и метка поля в середине строки — файл принят.

    Сценарий: порядок полей — перестановка от зерна, отличная от
    шаблонной; «Чем проверяется» — «тест …» на первой строке, «AC-<n>; не
    меняет файлов» на продолжении; «Текст» — две строки, на второй «Зоны:»
    в середине строки.

    Ловит мутацию: значение поля — только остаток первой строки (без
    продолжения) — «Чем проверяется» теряет AC-<n> и получает отказ формы;
    метка поля распознаётся в любом месте строки — «Зоны:» внутри «Текст»
    даёт повтор поля «Зоны» и отказ.
    """
    t = new_task(box)
    fields = good_fields(box)
    fields["Чем проверяется"] = (f"тест test_{box.word()}\n"
                                 f"AC-{box.rng.randint(1, 9)}; не меняет файлов")
    fields["Текст"] = (f"решено {box.word()}\n"
                       f"продолжение {box.word()}, Зоны: только {box.word()}")
    order = list(FIELDS)
    while order == list(FIELDS):
        box.rng.shuffle(order)

    ok, out = reject_decision(box, t, render([fields], order=order))

    assert_accepted(box, t, ok, out, 0)


# ---------------------------------------------------------------- AC-4


@pytest.mark.parametrize("field,values", [
    ("Утверждения о коде и поведении", ["не проверял, ответа нет",
                                        "проверено 04.11: 3 раза", "AC-3:1",
                                        "нет:2"]),
    ("Чем проверяется", ["тестом test_reject; не меняет файлов",
                         "AC-3 тестом test_reject"]),
    ("Существующие тесты", ["проверок нет", "tests/test_fsm_spec_gate_reject.py",
                            "все не ломаются"]),
    ("Зоны", ["в зонах", "расширить зоны fsm"]),
])
def test_ac4_field_not_in_form_refused(box, field, values):
    """Поле не по форме требования 2 — отказ с именем решения и поля, задача на `spec_gate`.

    Сценарий: для каждого значения `values` — файл из 1–2 решений, у
    решения со случайным номером поле `field` не по форме (числа с
    двоеточием, но не `файл:строка`; нет AC-<n> или пометки «временный
    дублёр»/«не меняет файлов»; нет перечня `tests/…` с «не ломаются»,
    «нет» или «мандат:»; нет «выполнимо в зонах SPEC» и пути с «/»).
    Отказ состояния не меняет — значения идут по одной задаче.

    Ловит мутацию: `файл:строка` распознаётся по любому «<что-то>:<число>»
    — «AC-3:1», «нет:2», «04.11: 3» проходят; «Существующие тесты»
    засчитывает путь без «не ломаются» — задача уходит в `spec_writing`.
    """
    t = new_task(box)
    for value in values:
        decisions = [good_fields(box) for _ in range(box.rng.randint(1, 2))]
        n = box.rng.randrange(len(decisions))
        decisions[n][field] = value

        ok, out = reject_decision(box, t, render(decisions))

        assert_refused(box, t, ok, f"[{value}]\n{out}", 0, f"Решение {n + 1}", field)


@pytest.mark.parametrize("field,values", [
    ("Утверждения о коде и поведении", ["  нет  ", "`orchestrator/fsm.py:1863`",
                                        "orchestrator/fsm.py:1863–1865",
                                        "см. fsm.py:1863, там проверка"]),
    ("Существующие тесты", [
        "  нет ", "`tests/test_fsm_spec_gate_reject.py` не ломаются",
        "tests/test_fsm_spec_gate_reject.py, tests/test_answer.py не ломаются"]),
    ("Зоны", ["`orchestrator/fsm.py`",
              "orchestrator/fsm.py, docs/operator-gates.md"]),
])
def test_ac4_field_in_form_passes(box, field, values):
    """Поле по форме — «нет» с пробелами вокруг, `файл:строка` в обратных кавычках, диапазоном и с запятой после, путь в кавычках и с запятой после — файл принят.

    Сценарий: значения `values` поля `field` подаются по очереди одной
    задаче: принятый возврат возвращает её на гейт, следующий файл
    ссылается в «Прежние решения» на номера принятых.

    Ловит мутацию: токен `файл:строка` или путь не отделяется от
    обрамляющих обратных кавычек и запятой после — «fsm.py:1863,» и
    «`tests/…py`» не засчитываются, файл получает отказ формы; «нет»
    сравнивается без снятия пробелов — «  нет  » отказ.
    """
    t = new_task(box)
    numbers: list = []
    for k, value in enumerate(values, 1):
        fields = good_fields(box, numbers)
        fields[field] = value

        ok, out = reject_decision(box, t, render([fields]))

        assert_accepted(box, t, ok, f"[{value}]\n{out}", k - 1)
        numbers.append(f"{k}.1")
        back_to_gate(box, t)


# ---------------------------------------------------------------- AC-5


def test_ac5_template_stub_refused(box):
    """Поле с дословной заглушкой шаблона (внешняя пара «<…>» целиком) — отказ с именем решения и поля; у «Существующие тесты» — по заглушке, не по мандату.

    Сценарий: для каждого из шести полей (порядок — от зерна) — файл из
    1–2 решений по форме, у решения со случайным номером поле — заглушка
    из шаблона ТЗ; отказ состояния не меняет — поля идут по одной
    задаче. У «Зоны» и
    «Утверждения…» заглушка сама содержит «выполнимо в зонах SPEC» и
    «опыт:», то есть проходит проверку формы — отказ даёт только
    распознавание заглушки. У «Существующие тесты» заглушка содержит
    «мандат: <строка мандата>»: отказ не называет «только мандат тестов».

    Ловит мутацию: заглушка не распознаётся (проверяется только форма) —
    поле «Зоны» с заглушкой проходит; проверка мандата идёт раньше
    заглушки — отказ «Существующие тесты» говорит «только мандат тестов».
    """
    t = new_task(box)
    assert set(STUBS) == set(FIELDS), f"заглушки шаблона ТЗ: {STUBS}"
    fields = list(FIELDS)
    box.rng.shuffle(fields)
    for field in fields:
        decisions = [good_fields(box) for _ in range(box.rng.randint(1, 2))]
        n = box.rng.randrange(len(decisions))
        decisions[n][field] = STUBS[field]

        ok, out = reject_decision(box, t, render(decisions))

        assert_refused(box, t, ok, f"[{field}]\n{out}", 0, f"Решение {n + 1}", field)
        if field == "Существующие тесты":
            assert ONLY_TESTS not in out, box.note(f"отказ по мандату:\n{out}")


@pytest.mark.parametrize("case", ["nested_experience", "angle_id", "comment"])
def test_ac5_nested_fragment_angle_brackets_and_comment_pass(box, case):
    """Вложенный фрагмент шаблона без внешней пары, прочие угловые скобки и HTML-комментарий шаблона заглушкой не считаются — файл принят.

    Сценарий: «Утверждения…» — «опыт: <что сделано и что увидено>»;
    «Текст» — с `<id>`; в файле — HTML-комментарий шаблона.

    Ловит мутацию: заглушкой считается любая пара «<…>» в поле — `<id>` в
    «Текст» и «опыт: <что сделано и что увидено>» получают отказ;
    HTML-комментарий не пропускается — строка «<!-- … «### Решение <n>» …»
    ломает разбор.
    """
    t = new_task(box)
    fields = good_fields(box)
    comment = False
    if case == "nested_experience":
        fields["Утверждения о коде и поведении"] = "опыт: <что сделано и что увидено>"
    elif case == "angle_id":
        fields["Текст"] = f"решено: reject <id> --decision {box.word()}"
    else:
        comment = True

    ok, out = reject_decision(box, t, render([fields], comment=comment))

    assert_accepted(box, t, ok, out, 0)


def test_ac5_nested_mandate_fragment_not_a_stub(box):
    """«Существующие тесты: мандат: <строка мандата>» без внешней пары — не заглушка: отказ даёт проверка мандата.

    Ловит мутацию: вложенный фрагмент «<строка мандата>» принят за
    заглушку — отказ по заглушке без «только мандат тестов».
    """
    t = new_task(box)
    fields = good_fields(box)
    fields["Существующие тесты"] = "мандат: <строка мандата>"

    ok, out = reject_decision(box, t, render([fields]))

    assert_refused(box, t, ok, out, 0, ONLY_TESTS)


# ---------------------------------------------------------------- AC-6


def test_ac6_prior_decisions_refused(box):
    """«Прежние решения» без ссылки на один из номеров, со ссылкой на несуществующий номер, без «противоречий нет», с «первое решение» при прежних возвратах или номерами без «№» — отказ с именем решения и поля.

    Сценарий: у задачи три прежних возврата — два текстом и один файлом
    из 2–3 решений, порядок от зерна (номера «k» и «k.n»). Для каждого
    случая (порядок от зерна) — новый файл из 1–2 решений, у решения со
    случайным номером поле «Прежние решения» испорчено: пропущен
    случайный номер; добавлен «№4»; «№k.(m+2)» у возврата файлом; «№k» у
    возврата файлом; «№k.1» у возврата текстом; нет «противоречий нет»;
    «первое решение» при всех ссылках; номера без «№». Отказ состояния не
    меняет — случаи идут по одной задаче.

    Ловит мутацию: ссылки сверяются только на полноту (лишняя ссылка не
    проверяется) — «№4», «№2.5» проходят; номер возврата файлом считается
    «k», а не «k.n» — «№k» проходит; «первое решение» засчитывается при
    прежних возвратах.
    """
    t = new_task(box)
    kinds = ["text", "text", "file"]
    box.rng.shuffle(kinds)
    numbers, files = seed_returns(box, t, kinds)
    file_k, m = next(iter(files.items()))
    text_k = box.rng.choice([k for k, kind in enumerate(kinds, 1)
                             if kind == "text"])
    refs = [f"№{n}" for n in numbers]
    box.rng.shuffle(refs)
    tail = ": противоречий нет"
    dropped = box.rng.choice(refs)
    cases = [
        ("missing", ", ".join(r for r in refs if r != dropped) + tail),
        ("nonexistent_k", ", ".join(refs + [f"№{len(kinds) + 1}"]) + tail),
        ("nonexistent_n", ", ".join(refs + [f"№{file_k}.{m + 2}"]) + tail),
        ("bare_file_k", ", ".join(refs + [f"№{file_k}"]) + tail),
        ("text_k_with_n", ", ".join(refs + [f"№{text_k}.1"]) + tail),
        ("no_contradictions", "сверено с " + ", ".join(refs)),
        ("first_with_prior", ", ".join(refs) + tail + "; первое решение по теме"),
        ("numbers_without_sign", ", ".join(numbers) + tail),
    ]
    box.rng.shuffle(cases)
    before = len(returns(box, t))
    for case, value in cases:
        decisions = [good_fields(box, numbers)
                     for _ in range(box.rng.randint(1, 2))]
        n = box.rng.randrange(len(decisions))
        decisions[n]["Прежние решения"] = value

        ok, out = reject_decision(box, t, render(decisions))

        assert_refused(box, t, ok, f"[{case}: {value}]\n{out}", before,
                       f"Решение {n + 1}", "Прежние решения")


@pytest.mark.parametrize("case", ["with_noise", "punctuation"])
def test_ac6_all_prior_numbers_with_noise_or_punctuation_pass(box, case):
    """Ссылки «№…» на все прежние номера и «противоречий нет» проходят — с «AC-3», датами и id задачи рядом и со знаком препинания сразу после ссылки.

    Сценарий: три прежних возврата (два текстом, один файлом, порядок от
    зерна). «with_noise» — ссылки через «, » и «AC-3», «04.11»,
    «2026-11-04», id задачи; «punctuation» — каждая ссылка с запятой
    после, последняя — с точкой («№2.1.»).

    Ловит мутацию: прочие числа принимаются за ссылки (даты, «AC-3») —
    «04.11» читается ссылкой на несуществующий номер; знак препинания
    входит в номер — «№2.1.» и «№1,» не совпадают с номерами, отказ.
    """
    t = new_task(box)
    kinds = ["text", "text", "file"]
    box.rng.shuffle(kinds)
    numbers, _files = seed_returns(box, t, kinds)
    refs = [f"№{n}" for n in numbers]
    box.rng.shuffle(refs)
    if case == "with_noise":
        value = (f"сверено ({t.id}, 04.11, 2026-11-04, AC-3) с "
                 + ", ".join(refs) + ": противоречий нет")
    else:
        value = " ".join(r + "," for r in refs[:-1]) + f" {refs[-1]}. противоречий нет"
    fields = good_fields(box, numbers)
    fields["Прежние решения"] = value
    before = len(returns(box, t))

    ok, out = reject_decision(box, t, render([fields]))

    assert_accepted(box, t, ok, out, before)


def test_ac6_first_decision_without_prior_returns_passes(box):
    """Без прежних возвратов «первое решение» проходит; ссылка «№1» при отсутствии возвратов — отказ.

    Ловит мутацию: «первое решение» запрещено всегда (или проверка
    «есть прежние» читает не журнал задачи) — первый файл получает
    отказ; ссылка на несуществующий номер при пустом перечне не
    проверяется — «№1» проходит.
    """
    t = new_task(box)
    bad = good_fields(box)
    bad["Прежние решения"] = "сверено с №1: противоречий нет"

    ok, out = reject_decision(box, t, render([bad]))

    assert_refused(box, t, ok, out, 0, "Решение 1", "Прежние решения")
    ok, out = reject_decision(box, t, render([good_fields(box)]))
    assert_accepted(box, t, ok, out, 0)


# ---------------------------------------------------------------- AC-7


def give_answer(box, t, marker: str, element: str) -> None:
    """`answer` на `spec_gate` со строкой мандата `marker element`, независимой проверкой и матрицей — принят."""
    row = (f"`{element}`", "фикстура сценария", "нет", "не покрыто", "ок")
    text = (f"Ответ Оператора {box.seed}.\n\n{marker} {element}\n\n"
            "Независимая проверка: матрица подтверждена\n\n"
            "## Матрица неослабления\n\n"
            "| " + " | ".join(MATRIX_HEADERS) + " |\n"
            + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")
    ok, out = cli(box, "answer", t.id, write_file(box, text))
    assert ok and state(box, t) == "spec_gate", box.note(f"answer не принят:\n{out}")


def comma_id(box, t, name: str) -> str:
    return project_profile.test_id("frontend", t.project.front_rel, name)


def mandate_decision(box, value: str) -> str:
    fields = good_fields(box)
    fields["Существующие тесты"] = value
    return render([fields])


def test_ac7_id_mandate_with_comma_passes_only_after_answer(box):
    """Мандат по идентификатору компонента с запятой в имени: до `answer` — отказ, после `answer` с той же строкой тот же файл принят.

    Сценарий: идентификатор теста компонента `frontend` учебного проекта
    (`project_profile.test_id`, имя с « > » и «, »). Файл решения —
    «Существующие тесты: мандат: Ослабление теста по идентификатору
    разрешено: <id>». Первый `reject --decision` — отказ с «Решение 1» и
    «Существующие тесты», задача на `spec_gate`; затем `answer` с этой
    строкой (настоящий ANSWER-1), тот же файл — принят, задача в
    `spec_writing`.

    Ловит мутацию: строка мандата решения не сверяется с ANSWER-n — файл
    проходит до `answer`; элементы ANSWER-n читаются `mandate.elements`
    (деление по запятой) — идентификатор с запятой не находится, файл не
    проходит и после `answer`.
    """
    t = new_task(box)
    cid = comma_id(box, t, f"{box.word()} {box.word()} > {box.word()}, "
                           f"{box.word()} {box.word()}")
    line = f"{mandate.TEST_ID_MANDATE_MARKER} {cid}"
    text = mandate_decision(box, f"мандат: {line}")

    ok, out = reject_decision(box, t, text)
    assert_refused(box, t, ok, out, 0, "Решение 1", "Существующие тесты")

    give_answer(box, t, mandate.TEST_ID_MANDATE_MARKER, cid)
    ok, out = reject_decision(box, t, text)
    assert_accepted(box, t, ok, out, 0)


def test_ac7_id_mandate_prefix_before_comma_refused(box):
    """В ANSWER-n один идентификатор «…::a, b», мандат решения называет только «…::a» — отказ с именем решения и поля.

    Ловит мутацию: `mandate.elements` вместо `mandate.id_elements` для
    обеих сторон — запятая делит идентификатор ANSWER-n на «…::a» и «b»,
    «…::a» находится среди элементов, и возврат проходит.
    """
    t = new_task(box)
    head = f"{box.word()} > {box.word()}"
    full = comma_id(box, t, f"{head}, {box.word()}")
    give_answer(box, t, mandate.TEST_ID_MANDATE_MARKER, full)
    text = mandate_decision(
        box, f"мандат: {mandate.TEST_ID_MANDATE_MARKER} {comma_id(box, t, head)}")

    ok, out = reject_decision(box, t, text)

    assert_refused(box, t, ok, out, 0, "Решение 1", "Существующие тесты")


@pytest.mark.parametrize("answered", ["both", "one"])
def test_ac7_two_mandate_lines_each_checked(box, answered):
    """Поле с двумя строками «мандат: …»: обе поданы `answer` — принят; подана одна — отказ с именем решения и поля.

    Сценарий: строка мандата по пути файла теста `frontend` и строка по
    идентификатору теста с запятой; ANSWER-n — на обе («both») или только
    на первую («one»), порядок строк в поле — от зерна.

    Ловит мутацию: проверяется только первая строка «мандат:» поля —
    вторая, не поданная `answer`, проходит.
    """
    t = new_task(box)
    cid = comma_id(box, t, f"{box.word()} > {box.word()}, {box.word()}")
    lines = [(mandate.TEST_WEAKENING_MANDATE_MARKER, t.project.front_rel),
             (mandate.TEST_ID_MANDATE_MARKER, cid)]
    give_answer(box, t, *lines[0])
    if answered == "both":
        give_answer(box, t, *lines[1])
    box.rng.shuffle(lines)
    text = mandate_decision(box, "\n".join(f"мандат: {marker} {element}"
                                           for marker, element in lines))

    ok, out = reject_decision(box, t, text)

    if answered == "both":
        assert_accepted(box, t, ok, out, 0)
    else:
        assert_refused(box, t, ok, out, 0, "Решение 1", "Существующие тесты")


def test_ac7_text_after_mandate_line_is_part_of_it(box):
    """Текст после строки мандата в той же физической строке входит в неё: непутевой хвост, которого нет в ANSWER-n, — отказ.

    Сценарий: ANSWER-1 — «Ослабление тестов разрешено: <путь теста>»;
    поле — «мандат: Ослабление тестов разрешено: <путь теста>; tests/a.py
    не ломаются».

    Ловит мутацию: строка мандата обрезается по «;» или по первому
    пробелу после элемента — элемент совпадает с ANSWER-n, возврат
    проходит.
    """
    t = new_task(box)
    rel = t.project.front_rel
    give_answer(box, t, mandate.TEST_WEAKENING_MANDATE_MARKER, rel)
    text = mandate_decision(box, f"мандат: {mandate.TEST_WEAKENING_MANDATE_MARKER} "
                                 f"{rel}; tests/a.py не ломаются")

    ok, out = reject_decision(box, t, text)

    assert_refused(box, t, ok, out, 0, "Решение 1", "Существующие тесты")


def test_ac7_non_test_mandate_refused(box):
    """Строка мандата зон, зависимостей мержа или без известного маркера — отказ «на spec_gate — только мандат тестов» с именем решения и поля.

    Сценарий: три файла по одной задаче (отказ состояния не меняет) —
    «мандат: Расширение зон разрешено: <путь>», «мандат: Зависимости
    мержа: нет», «мандат: Разрешено всё: <слово>».

    Ловит мутацию: строка без маркера мандата тестов молча пропускается
    (элементов нет — сверять нечего) — возврат проходит; мандат зон
    сверяется с ANSWER-n как мандат тестов — текста «только мандат
    тестов» в отказе нет.
    """
    t = new_task(box)
    for line in (f"Расширение зон разрешено: {t.project.front_rel}",
                 "Зависимости мержа: нет", f"Разрешено всё: {box.word()}"):
        ok, out = reject_decision(box, t, mandate_decision(box, f"мандат: {line}"))

        assert_refused(box, t, ok, f"[{line}]\n{out}", 0, ONLY_TESTS,
                       "Решение 1", "Существующие тесты")


# ---------------------------------------------------------------- AC-8


def seed_listed_returns(box, t) -> list[dict]:
    """Четыре прежних возврата в порядке от зерна: длинный текстом, текстом с переносом, файлом из двух решений (одно «Текст» в две строки), запись с заголовком, но не по форме."""
    words = []
    while len(" ".join(words)) < 125:
        words.append(box.word())
    kinds = ["long", "newline", "file", "header"]
    box.rng.shuffle(kinds)
    items: list[dict] = []
    numbers: list[str] = []
    for k, kind in enumerate(kinds, 1):
        if kind == "long":
            tail = box.word()
            reason = " ".join(words) + " " + tail
            text_return(box, t, reason)
            items.append({"number": str(k), "parts": [reason[:30]], "absent": tail})
            numbers.append(str(k))
        elif kind == "newline":
            parts = [f"{box.word()} {box.word()}", f"{box.word()} {box.word()}"]
            text_return(box, t, "\n".join(parts))
            items.append({"number": str(k), "parts": parts})
            numbers.append(str(k))
        elif kind == "file":
            decisions = [good_fields(box, numbers), good_fields(box, numbers)]
            parts = [f"{box.word()} {box.word()}", f"{box.word()} {box.word()}"]
            decisions[0]["Текст"] = "\n".join(parts)
            file_return(box, t, decisions)
            items.append({"number": f"{k}.1", "parts": parts})
            items.append({"number": f"{k}.2", "parts": [decisions[1]["Текст"]]})
            numbers += [f"{k}.1", f"{k}.2"]
        else:
            part = f"{box.word()} {box.word()}"
            store.set_state(box.conn, t.id, "spec_writing", "operator",
                            expected_state="spec_gate",
                            detail=f"{PREFIX}{HEADER}\n\n{part}")
            back_to_gate(box, t)
            items.append({"number": str(k), "parts": [part],
                          "not_number": f"{k}.1"})
            numbers.append(str(k))
    box.listed_numbers = numbers
    return items


def assert_listed(box, out: str, items: list[dict]) -> None:
    for item in items:
        line = line_with(out, item["parts"][0])
        why = box.note(f"{item}: строка «{line}»\nвывод:\n{out}")
        assert line, why
        for part in item["parts"]:
            assert part in line, why
        assert has_number(line, item["number"]), why
        if "not_number" in item:
            assert not has_number(line, item["not_number"]), why
        if "absent" in item:
            assert item["absent"] not in out, why


@pytest.mark.parametrize("channel", ["refusal", "auto"])
def test_ac8_prior_decisions_listed(box, channel):
    """Отказ `reject --decision` по содержанию файла и остановка `auto` на `spec_gate` перечисляют прежние решения: «k.n» и «Текст» у возврата файлом, «k» и не более 120 знаков у прочих, переносы свёрнуты.

    Сценарий: четыре прежних возврата (порядок от зерна): текстом длиннее
    120 знаков с уникальным словом после 120-го знака; текстом в две
    строки; файлом из двух решений («Текст» первого — две строки); запись
    возврата с заголовком файла решения, но не по форме (журнал пульта
    до задачи). «refusal» — файл решения без поля «Зоны»; «auto» —
    `auto.cmd_auto`. Каждое прежнее решение — в одной строке вывода
    вместе со своим номером; слово после 120-го знака не напечатано;
    запись с заголовком — номером «k», не «k.1». Вывод `auto` называет
    `--decision`.

    Ловит мутацию: номер «k.n» получает любая запись, начинающаяся
    заголовком, без разбора формы — запись не по форме печатается
    «k.1»; переносы строк не свёрнуты — части «Текст» на разных строках;
    причина печатается целиком — слово после 120-го знака в выводе.
    """
    t = new_task(box)
    items = seed_listed_returns(box, t)
    if channel == "refusal":
        fields = good_fields(box, box.listed_numbers)
        fields["Зоны"] = None
        before = len(returns(box, t))
        ok, out = reject_decision(box, t, render([fields]))
        assert_refused(box, t, ok, out, before, "Зоны")
    else:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
                mock.patch("orchestrator.runner.cmd_run",
                           side_effect=AssertionError("шаг роли на spec_gate")):
            auto.cmd_auto(t.id)
        out = buf.getvalue()
        assert state(box, t) == "spec_gate", box.note(out)
        assert "--decision" in out, box.note(f"подсказка без --decision:\n{out}")
    assert_listed(box, out, items)


def test_ac8_command_refusals_print_no_list(box):
    """Отказы команды (AC-12…AC-15) перечня прежних решений не печатают.

    Сценарий: у задачи прежний возврат текстом (уникальная причина) и
    возврат файлом (уникальный «Текст»); затем по очереди отказы
    команды: `--decision` без значения, несуществующий файл, ключ вместе
    с причиной, `--decision` в `in_dev` (последним). В выводе каждого
    отказа нет ни причины, ни «Текст».

    Ловит мутацию: перечень печатается в общей голове отказов `reject
    --decision`, до разбора аргументов — он появляется и в отказе
    «--decision без значения».
    """
    t = new_task(box)
    reason = f"причина {box.word()} {box.word()}"
    text_return(box, t, reason)
    fields = good_fields(box, ["1"])
    file_return(box, t, [fields])
    path = write_file(box, render([good_fields(box, ["1", "2.1"])]))
    for case, argv in (
            ("no_value", ["reject", t.id, "--decision"]),
            ("missing_file", ["reject", t.id, "--decision",
                              str(box.root / f"net-{box.word()}.md")]),
            ("with_reason", ["reject", t.id, f"причина {box.word()}",
                             "--decision", path]),
            ("other_state", ["reject", t.id, "--decision", path])):
        if case == "other_state":
            store.update_task(box.conn, t.id, state="in_dev")
        before_state = state(box, t)

        ok, out = cli(box, *argv)

        why = box.note(f"[{case}] вывод:\n{out}")
        assert not ok, why
        assert state(box, t) == before_state, why
        assert reason not in out, why
        assert fields["Текст"] not in out, why


def test_ac8_help_names_decision_form(box):
    """Справка `artel.py --help` называет форму `reject <id> --decision <файл>`.

    Ловит мутацию: ключ добавлен в разбор, а строка справки команды
    осталась прежней `reject <id> "<причина>"` — формы в справке нет.
    """
    ok, out = cli(box, "--help")

    assert ok, box.note(out)
    assert "reject <id> --decision <файл>" in out, box.note(out[:4000])


# ---------------------------------------------------------------- AC-9


def test_ac9_text_reject_still_returns_with_warning(box):
    """Прежняя форма `reject <id> "<причина>"` на `spec_gate` возвращает задачу в `spec_writing` и печатает предупреждение.

    Ловит мутацию: предупреждение печатается только при ошибке, а не на
    каждом возврате текстом — его нет в выводе; прежняя форма отключена
    в пользу `--decision` — отказ.
    """
    t = new_task(box)
    reason = f"причина {box.word()}\n{box.word()}"

    ok, out = cli(box, "reject", t.id, reason)

    assert_accepted(box, t, ok, out, 0, text=reason)
    assert returns(box, t)[-1] == PREFIX + reason, box.note(str(returns(box, t)))
    assert WARNING in out, box.note(f"нет предупреждения:\n{out}")


def test_ac9_text_reason_with_decision_header_refused(box):
    """Причина, первая непустая строка которой — заголовок файла решения, — отказ «файл решения подаётся ключом --decision», задача на `spec_gate`, журнал не пополнен.

    Сценарий: причина — текст файла решения по форме, перед заголовком
    по очереди: ничего, пустые строки, пробелы и табуляция — по одной
    задаче.

    Ловит мутацию: заголовок ищется `reason.startswith(HEADER)` без
    пропуска пустых строк и пробелов — причина с пустыми строками до
    заголовка уходит в журнал прежней формой.
    """
    t = new_task(box)
    for lead in ("", "\n\n", "  \n \t"):
        reason = lead + render([good_fields(box)])

        ok, out = cli(box, "reject", t.id, reason)

        assert_refused(box, t, ok, f"[{lead!r}]\n{out}", 0, HEADER_REFUSAL)


# --------------------------------------------------------------- AC-11


def test_ac11_parser_module_has_no_templates_and_no_file_reads():
    """В синтаксическом дереве `orchestrator/spec_gate_decision.py` нет идентификатора и строкового литерала с «templates» (без учёта регистра) и нет вызовов `open`, `.open`, `read_text`, `read_bytes`.

    Сценарий: модуль находится импортной машинерией, его текст
    разбирается `ast`; обходятся имена, атрибуты, имена функций,
    классов, аргументов, импортов и ключевых слов, строковые константы
    (в том числе докстроки и части f-строк) и вызовы.

    Ловит мутацию: разбор читает заглушки из
    `config.TEMPLATES / "SPEC-GATE-DECISION.md"` через `read_text` —
    в дереве атрибут `TEMPLATES` и вызов `read_text`.
    """
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None and spec.origin, f"модуля {MODULE} нет"
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Name):
            names = [node.id]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.arg):
            names = [node.arg]
        elif isinstance(node, ast.alias):
            names = [node.name, node.asname or ""]
        elif isinstance(node, ast.keyword):
            names = [node.arg or ""]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names = [node.value]
        found += [(node.lineno, name) for name in names
                  if "templates" in name.casefold()]
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "open") or (
                    isinstance(func, ast.Attribute)
                    and func.attr in ("open", "read_text", "read_bytes")):
                found.append((node.lineno, ast.unparse(func)))
    assert found == [], f"{spec.origin}: {found}"


def test_ac11_parse_outcome_independent_of_template_file(box):
    """Результат разбора того же файла решения не зависит от файла шаблона в `config.TEMPLATES`: шаблон из ТЗ, удалён, изменён — исход прежний.

    Сценарий: два файла — по форме и с заглушкой шаблона в поле «Зоны»
    (заглушка проходит проверку формы, отказ даёт только знание
    заглушки). Для каждого состояния каталога шаблонов песочницы
    (шаблон из ТЗ; файла нет; заглушки в нём заменены другим текстом)
    — новая задача и оба файла: файл по форме принят, файл с заглушкой —
    отказ; текст отказа (с id задачи, заменённым меткой) одинаков во
    всех трёх состояниях.

    Ловит мутацию: заглушки читаются из файла шаблона во время работы —
    без файла (или с изменённым) заглушка «Зоны» не распознаётся, файл с
    ней принят.
    """
    good = render([good_fields(box)])
    stubbed_fields = good_fields(box)
    stubbed_fields["Зоны"] = STUBS["Зоны"]
    stubbed = render([stubbed_fields])
    template = box.templates / TEMPLATE_NAME
    outcomes = []
    for variant in ("template", "removed", "changed"):
        if variant == "removed":
            template.unlink()
        elif variant == "changed":
            template.write_text(TEMPLATE_TEXT.replace(
                STUBS["Зоны"], f"<{box.word()}>"), encoding="utf-8")
        t = new_task(box)
        ok_bad, out_bad = reject_decision(box, t, stubbed)
        bad = (ok_bad, state(box, t), out_bad.replace(t.id, "<id>"))
        ok_good, out_good = reject_decision(box, t, good)
        outcomes.append((variant, bad, (ok_good, state(box, t))))
    first = outcomes[0]
    assert first[1][:2] == (False, "spec_gate"), box.note(str(first))
    assert first[2] == (True, "spec_writing"), box.note(str(first))
    for other in outcomes[1:]:
        assert other[1:] == first[1:], box.note(f"{first}\n{other}")


# --------------------------------------------------------- AC-12…AC-15


def test_ac12_decision_without_value_refused(box):
    """`reject <id> --decision` без значения — отказ, состояние и журнал возврата прежние.

    Ловит мутацию: ключ без значения берётся текстом причины
    «--decision» — задача уходит в `spec_writing` прежней формой.
    """
    t = new_task(box)

    ok, out = cli(box, "reject", t.id, "--decision")

    assert_refused(box, t, ok, out, 0)


def test_ac13_missing_or_unreadable_file_refused(box):
    """`reject <id> --decision <файл>` с несуществующим или нечитаемым файлом — отказ, состояние и журнал возврата прежние.

    Сценарий: по одной задаче (отказ состояния не меняет) — путь
    несуществующего файла, путь каталога и, если процесс не root, файл
    по форме без права чтения.

    Ловит мутацию: ошибка чтения файла не перехвачена либо подменена
    пустым текстом и тихим проходом — исключение вместо отказа или
    возврат без текста.
    """
    t = new_task(box)
    target = box.root / f"katalog-{box.word()}"
    target.mkdir()
    paths = [("missing", str(box.root / f"net-{box.word()}.md")),
             ("directory", str(target))]
    if not (hasattr(os, "geteuid") and os.geteuid() == 0):
        locked = write_file(box, render([good_fields(box)]))
        os.chmod(locked, 0)
        paths.append(("no_read_permission", locked))
    for case, path in paths:
        ok, out = cli(box, "reject", t.id, "--decision", path)

        assert_refused(box, t, ok, f"[{case}]\n{out}", 0)


def test_ac14_decision_with_positional_reason_refused(box):
    """Ключ `--decision` вместе с позиционной причиной — отказ, состояние и журнал возврата прежние.

    Сценарий: файл по форме; причина до ключа и после значения ключа —
    по одной задаче.

    Ловит мутацию: при ключе позиционная причина молча отбрасывается —
    файл по форме принимается, задача уходит в `spec_writing`.
    """
    t = new_task(box)
    path = write_file(box, render([good_fields(box)]))
    reason = f"причина {box.word()}"
    for argv in (["reject", t.id, reason, "--decision", path],
                 ["reject", t.id, "--decision", path, reason]):
        ok, out = cli(box, *argv)

        assert_refused(box, t, ok, f"{argv}\n{out}", 0)


def test_ac15_decision_outside_spec_gate_refused(box):
    """`reject <id> --decision <файл>` вне `spec_gate`, в том числе в `awaiting_human`, — отказ «--decision применим только на spec_gate», состояние прежнее.

    Сценарий: одна задача по очереди ставится (строкой БД) в
    `awaiting_human`, `in_dev`, `acceptance`, `merge_gate`, `verifying`,
    `spec_writing`, `review` (порядок от зерна); в каждом —
    `reject --decision` с файлом по форме.

    Ловит мутацию: проверка `--decision` стоит после проверки
    `awaiting_human` — в `awaiting_human` отказ говорит об ожидании людей
    проекта, текста «--decision применим только на spec_gate» нет; в
    `acceptance` файл берётся причиной отказа приёмки — задача уходит в
    `in_dev`.
    """
    t = new_task(box)
    path = write_file(box, render([good_fields(box)]))
    others = ["awaiting_human", "in_dev", "acceptance", "merge_gate",
              "verifying", "spec_writing", "review"]
    box.rng.shuffle(others)
    for other in others:
        store.update_task(box.conn, t.id, state=other)

        ok, out = cli(box, "reject", t.id, "--decision", path)

        why = box.note(f"[{other}] вывод:\n{out}")
        assert not ok, why
        assert state(box, t) == other, why
        assert STATE_REFUSAL in out, why
