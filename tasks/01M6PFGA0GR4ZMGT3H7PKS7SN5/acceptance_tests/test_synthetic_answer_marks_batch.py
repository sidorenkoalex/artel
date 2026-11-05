"""Синтетический ответ канарейки на батч вопросов аналитика ставит признак
«батч вопросов отвечен» тем же узлом, что `approve` (AC-1 — AC-4).

Группа: разовый

Красен до реализации: `canary._pass_escalated_with_synthetic_answer` не зовёт `fsm._mark_questions_answered` — строки `fsm.QUESTIONS_ANSWERED_ACTION` после синтетического ответа нет (AC-1), и следующий `advance` из `spec_writing` эскалирует тот же батч снова (AC-2); зелены с рождения AC-3 и AC-4 — признака нет и сегодня, они держат условие вызова и отсутствие батча.

Разовый, а не долгоживущий: шов, который SPEC называет («Материалы» —
`canary._pass_escalated_with_synthetic_answer`,
`fsm._mark_questions_answered`), — закрытые имена `orchestrator`, а их
вызов долгоживущему файлу `tests/` запрещён; тот же приём, что у
`tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py` (закрытые имена
канарейки — в разовом файле планки).

Связка: «канарейка (`_pass_escalated_with_synthetic_answer`) — журнал
задачи — документы задачи — переход `fsm.cmd_advance` из `spec_writing`»
в `tests.sandbox.LightTransitionSandbox` (фикстура `light_transition`):
документы задачи лежат на диске временного каталога песочницы
(`self.tdir`), песочница читает их как ветку документов. Синтетический
ANSWER пишется путём (1) Решения 2 Оператора: канал
`canary.answer.cmd_answer` подменён и сам кладёт `ANSWER-<n>.md`
(`n` — следующий за наибольшим номером) с текстом, который отдала
канарейка. Шаг аналитика — запись журнала `analyst` / `agent run
finished`, как в `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`.
Текст батча (кириллица) и число ANSWER до эскалации при
`answer_baseline > 0` — из `random`; зерно печатается и входит в текст
провала.

Провалидирован временным стабом реализации (вызов
`fsm._mark_questions_answered` при условии approve до `store.set_state`;
откачен, не закоммичен): все тесты зелены; мутанты стаба «baseline по
истинности», «вызов удалён», «вызов безусловный», «только
escalated_from», «только answer_baseline» красят свои тесты.
"""
import hashlib
import random
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import canary, fsm, fsm_advance, store

CYRILLIC = "абвгдежзиклмнопрстуфхцчшэюя"

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: батч {marker}

## Вопросы

1. **Вопрос «{marker}»?**
   - A) да, {marker}
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - B) нет
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - дефолт: A.
"""

ANSWER_TEXT = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

1. A.
"""

SPEC_DRAFT = """---
task: {task}
type: spec
author_role: analyst
status: draft
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура синтетического ответа

## Контекст

Фикстура.

## Требования

1. Требование фикстуры.

## Критерии приёмки

AC-1. Критерий фикстуры.

## Не входит

Ничего.
"""

TZ_TEXT = """# ТЗ фикстуры

Сделать фикстуру.
"""


@pytest.fixture
def rng():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    generator = random.Random(seed)
    generator.seed_value = seed
    return generator


def answer_numbers(sb) -> list:
    return sorted(int(p.name[len("ANSWER-"):-len(".md")])
                  for p in sb.tdir.glob("ANSWER-*.md")
                  if p.name[len("ANSWER-"):-len(".md")].isdigit())


def put_answer(sb, n: int, text: str | None = None) -> None:
    sb.tdir.mkdir(parents=True, exist_ok=True)
    (sb.tdir / f"ANSWER-{n}.md").write_text(
        text if text is not None else ANSWER_TEXT.format(task=sb.TASK, n=n),
        encoding="utf-8")


def put_questions(sb, rng) -> str:
    marker = "".join(rng.choice(CYRILLIC) for _ in range(8))
    text = QUESTIONS_TEXT.format(task=sb.TASK, marker=marker)
    sb.tdir.mkdir(parents=True, exist_ok=True)
    (sb.tdir / "QUESTIONS.md").write_text(text, encoding="utf-8")
    return text


def escalate_canary_task(sb, escalated_from: str, baseline) -> None:
    """Задача песочницы — канареечная, в `escalated` с полями эскалации;
    до эскалации у неё `baseline` ANSWER (0, если `baseline` не число)."""
    sb.tdir.mkdir(parents=True, exist_ok=True)
    (sb.tdir / "TZ.md").write_text(TZ_TEXT, encoding="utf-8")
    for n in range(1, (baseline or 0) + 1):
        put_answer(sb, n)
    conn = store.db()
    store.update_task(conn, sb.TASK, is_canary=1)
    sb.set_state("escalated")
    store.update_task(conn, sb.TASK, escalated_from=escalated_from,
                      answer_baseline=baseline)


def synthetic_pass(sb) -> tuple:
    """`_pass_escalated_with_synthetic_answer` с подменённым каналом ANSWER:
    (номер записанного ANSWER, индекс первой новой записи журнала, исключение
    или None)."""
    written = []

    def channel(task_id, file_path, *args, **kwargs):
        numbers = answer_numbers(sb)
        n = (numbers[-1] if numbers else 0) + 1
        put_answer(sb, n, Path(file_path).read_text(encoding="utf-8"))
        written.append(n)

    start = len(store.task_steps(store.db(), sb.TASK))
    error = None
    with mock.patch.object(canary.answer, "cmd_answer", side_effect=channel):
        try:
            canary._pass_escalated_with_synthetic_answer(store.db(), sb.TASK)
        except Exception as exc:  # провал — с текстом исключения в тесте
            error = exc
    return (written[0] if written else None), start, error


def steps(sb) -> list:
    return list(store.task_steps(store.db(), sb.TASK))


def note(sb, rng, text: str = "") -> str:
    rows = "\n".join(f"  {r['actor']} | {r['action']} | {r['detail']}"
                     for r in steps(sb))
    return f"{text}\nжурнал {sb.TASK}:\n{rows}\n(зерно: {rng.seed_value})"


def answered_indexes(sb, start: int) -> list:
    return [i for i, r in enumerate(steps(sb))
            if i >= start and r["action"] == fsm.QUESTIONS_ANSWERED_ACTION]


def baseline_value(kind: str, rng) -> int:
    return 0 if kind == "ноль" else rng.randrange(1, 5)


@pytest.mark.parametrize("kind", ["ноль", "больше нуля"])
def test_ac1_synthetic_answer_writes_batch_mark_before_state_change(
        light_transition, rng, kind):
    """Синтетический ответ на эскалацию батча из `spec_writing` пишет одну строку признака до смены состояния.

    Сценарий: канареечная задача в `escalated` из `spec_writing`,
    `answer_baseline` — `0` (ANSWER до эскалации не было) либо k > 0
    (до эскалации лежат ANSWER-1..k), в документах — `QUESTIONS.md`.
    После `_pass_escalated_with_synthetic_answer` в новых записях журнала
    ровно одна строка `fsm.QUESTIONS_ANSWERED_ACTION` с detail
    `sha256=<sha256 UTF-8 текста QUESTIONS.md>; ANSWER-<номер только что
    записанного синтетического ANSWER>`, она раньше записи
    `state -> spec_writing`, задача в `spec_writing`.

    Ловит мутацию: признак не ставится (вызова
    `fsm._mark_questions_answered` нет) — строки признака нет в обоих
    случаях; `answer_baseline` проверяется по истинности, а не
    `is not None` — в случае `0` строки нет; признак ставится после
    `store.set_state` — строка позже записи `state -> spec_writing`.
    """
    sb = light_transition
    baseline = baseline_value(kind, rng)
    escalate_canary_task(sb, "spec_writing", baseline)
    text = put_questions(sb, rng)

    number, start, error = synthetic_pass(sb)

    assert error is None, note(sb, rng, f"синтетический ответ упал: {error!r}")
    assert number == baseline + 1, note(sb, rng, "канал ANSWER не вызван")
    marks = answered_indexes(sb, start)
    assert len(marks) == 1, note(sb, rng, "новых строк признака не одна")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rows = steps(sb)
    assert rows[marks[0]]["detail"] == f"sha256={sha}; ANSWER-{number}", \
        note(sb, rng, "detail признака не тот")
    returns = [i for i, r in enumerate(rows)
               if i >= start and r["action"] == "state -> spec_writing"]
    assert returns, note(sb, rng, "записи о смене состояния нет")
    assert marks[0] < returns[0], note(
        sb, rng, "признак записан не раньше смены состояния")
    assert sb.state() == "spec_writing", note(sb, rng)


@pytest.mark.parametrize("kind", ["ноль", "больше нуля"])
def test_ac2_analyst_step_after_synthetic_answer_skips_same_batch(
        light_transition, rng, kind):
    """После синтетического ответа и шага аналитика тот же батч не эскалирует снова.

    Сценарий AC-1 (`answer_baseline` `0` либо k > 0), затем шаг аналитика
    (запись журнала `analyst` / `agent run finished`), `QUESTIONS.md` тот
    же, SPEC.md в черновике; `fsm.cmd_advance`. Задача не в `escalated`, в
    журнале есть строка `fsm_advance.QUESTIONS_SKIPPED_ACTION`.

    Ловит мутацию: вызов `fsm._mark_questions_answered` удалён из
    `_pass_escalated_with_synthetic_answer` — признака нет, `spec_writing`
    эскалирует тот же `QUESTIONS.md` (задача в `escalated`, строки пропуска
    нет), как в прогоне 03.11.
    """
    sb = light_transition
    escalate_canary_task(sb, "spec_writing", baseline_value(kind, rng))
    put_questions(sb, rng)
    _number, _start, error = synthetic_pass(sb)
    assert error is None, note(sb, rng, f"синтетический ответ упал: {error!r}")
    assert sb.state() == "spec_writing", note(sb, rng)
    (sb.tdir / "SPEC.md").write_text(SPEC_DRAFT.format(task=sb.TASK),
                                     encoding="utf-8")
    store.journal(store.db(), sb.TASK, "analyst", "agent run finished", "rc=0")
    start = len(steps(sb))

    try:
        out = sb.capture(fsm.cmd_advance, sb.TASK)
    except SystemExit as exc:
        out = f"SystemExit: {exc.code}"

    assert sb.state() != "escalated", note(sb, rng, f"батч эскалирован:\n{out}")
    skipped = [r for r in steps(sb)[start:]
               if r["action"] == fsm_advance.QUESTIONS_SKIPPED_ACTION]
    assert skipped, note(sb, rng, f"строки пропуска батча нет:\n{out}")


@pytest.mark.parametrize("escalated_from, baseline", [
    ("spec_writing", None),
    ("in_dev", 0),
])
def test_ac3_mark_not_written_when_half_of_condition_fails(
        light_transition, rng, escalated_from, baseline):
    """Признака нет, если не выполнена одна половина условия approve; возврат прежний.

    Сценарий (всё остальное условие AC-1 выполнено: `QUESTIONS.md` в
    документах, синтетический ANSWER записан после эскалации):
    (а) `escalated_from = spec_writing`, `answer_baseline = None`;
    (б) `escalated_from = in_dev`, `answer_baseline = 0`. После
    `_pass_escalated_with_synthetic_answer` новой строки
    `fsm.QUESTIONS_ANSWERED_ACTION` нет, задача в `escalated_from`.

    Ловит мутацию: вызов признака безусловный — строка в обоих случаях;
    проверяется только `escalated_from` — строка в (а); проверяется только
    `answer_baseline` — строка в (б).
    """
    sb = light_transition
    escalate_canary_task(sb, escalated_from, baseline)
    put_questions(sb, rng)

    number, start, error = synthetic_pass(sb)

    assert error is None, note(sb, rng, f"синтетический ответ упал: {error!r}")
    assert number is not None, note(sb, rng, "канал ANSWER не вызван")
    assert answered_indexes(sb, start) == [], note(
        sb, rng, "строка признака при невыполненном условии")
    assert sb.state() == escalated_from, note(sb, rng)


def test_ac4_no_questions_file_no_mark_and_return_as_before(
        light_transition, rng):
    """Без `QUESTIONS.md` в документах признака нет, функция не падает, задача в `spec_writing`.

    Сценарий: эскалация из `spec_writing` с `answer_baseline = 0`,
    синтетический ANSWER записан, `QUESTIONS.md` в документах задачи нет.
    После `_pass_escalated_with_synthetic_answer` исключения нет, строки
    `fsm.QUESTIONS_ANSWERED_ACTION` нет, задача в `spec_writing`.

    Ловит мутацию: хэш батча считается от непрочитанного файла (текст
    `None` не обработан) — исключение, задача остаётся в `escalated`;
    отсутствие батча подменено пустым текстом — строка признака с хэшем
    пустой строки.
    """
    sb = light_transition
    escalate_canary_task(sb, "spec_writing", 0)
    assert not (sb.tdir / "QUESTIONS.md").exists(), note(sb, rng)

    number, start, error = synthetic_pass(sb)

    assert error is None, note(sb, rng, f"синтетический ответ упал: {error!r}")
    assert number is not None, note(sb, rng, "канал ANSWER не вызван")
    assert answered_indexes(sb, start) == [], note(
        sb, rng, "строка признака без QUESTIONS.md")
    assert sb.state() == "spec_writing", note(sb, rng)
