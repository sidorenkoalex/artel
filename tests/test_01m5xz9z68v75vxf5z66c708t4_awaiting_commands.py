"""Команды Оператора по задаче в `awaiting_human`: отказ `approve`/`reject`/`answer` и `amend-tests` с подсказкой mr-sync, возврат из эскалации в `awaiting_human`.

Группа: долгоживущий
Красен до реализации: состояния `awaiting_human` пульт не знает — `approve` печатает «нечего подтверждать», `reject` и `answer` отказывают своим прежним текстом без подсказки mr-sync, `amend-tests` не проверяет состояние вовсе.

Песочница — `light_transition` (`LightTransitionSandbox`: задача артели,
заведённая `cmd_new`, `gitcmd.git` — `fake_git`, `gitcmd.in_repo` —
подмена с хуками `in_repo_handlers`). Состояние `awaiting_human` ставится
прямой установкой в БД (SPEC: «состояние — прямой установкой в
песочнице»). Свойство держит связку «команда — FSM — база»: команда
читает состояние строки задачи и не двигает его. Основание отказа и текст
ответа порождаются модулем `random` при каждом запуске; зерно печатается
и входит в текст провала.
"""
import contextlib
import io
import random

import pytest

from orchestrator import amend, answer, config, fsm, store

STATE = "awaiting_human"
HINT = "состояние ждёт людей проекта — mr-sync (шаг Б2.2)"
WORDS = ("ветка", "ревью", "проект", "люди", "слияние", "основание", "правка")


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def sandbox(light_transition, monkeypatch):
    """Лёгкая песочница без роли в окружении: команды идут от Оператора."""
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    return light_transition


def words(rng: random.Random) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(rng.randrange(2, 6)))


def run(fn, *args) -> str:
    """Вывод команды (stdout, stderr и текст `SystemExit`) одной строкой;
    исключение иного рода — провал теста."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


def operator_command(name: str, sb, rng: random.Random):
    """(функция, аргументы) команды Оператора `name` по задаче песочницы."""
    if name == "approve":
        return fsm.cmd_approve, (sb.TASK,)
    if name == "reject":
        return fsm.cmd_reject, (sb.TASK, words(rng))
    path = sb.root / f"answer-{rng.randrange(10 ** 6)}.md"
    path.write_text(f"Ответ Оператора: {words(rng)}\n", encoding="utf-8")
    return answer.cmd_answer, (sb.TASK, str(path))


@pytest.mark.parametrize("command", ["approve", "reject", "answer"])
def test_ac4_operator_command_refused_with_mr_sync_hint(sandbox, seed, command):
    """`approve`, `reject`, `answer` по задаче в `awaiting_human` отказывают с подсказкой mr-sync.

    Сценарий: задача песочницы переведена в `awaiting_human`; команда
    Оператора (`fsm.cmd_approve`, `fsm.cmd_reject` со случайным
    основанием, `answer.cmd_answer` со случайным файлом ответа) печатает
    или выходит с текстом, содержащим «состояние ждёт людей проекта —
    mr-sync (шаг Б2.2)»; задача остаётся в `awaiting_human`, новой записи
    `state -> …` в журнале нет.

    Ловит мутацию: отказ добавлен только в одну-две из трёх команд —
    оставшаяся отвечает прежним текстом («нечего подтверждать»,
    «reject применим только…», «answer доступна только…») без подсказки;
    `approve` пропускает `awaiting_human` дальше и переводит задачу в
    другое состояние; подсказка написана иначе (без «mr-sync» или без
    «Б2.2»).
    """
    rng = random.Random(seed)
    sandbox.set_state(STATE)
    rows_before = len(store.task_steps(store.db(), sandbox.TASK))
    fn, args = operator_command(command, sandbox, rng)
    out = run(fn, *args)
    note = f"зерно: {seed}; команда {command}"
    assert HINT in out, f"{note}: подсказки нет:\n{out}"
    assert sandbox.state() == STATE, f"{note}: состояние {sandbox.state()}"
    moved = [r["action"] for r in store.task_steps(store.db(), sandbox.TASK)[rows_before:]
             if (r["action"] or "").startswith("state -> ")]
    assert moved == [], f"{note}: переход в журнале: {moved}"


def test_ac9_amend_tests_refused_first_without_commit_or_push(sandbox, seed):
    """`amend-tests` по задаче в `awaiting_human` отказывает в начале с подсказкой mr-sync — без коммита и отправки.

    Сценарий: задача песочницы в `awaiting_human` с зафиксированным
    локом планки (случайный `tests_locked_sha` — без него команда
    отказывала бы раньше по своей причине);
    `amend.cmd_amend_tests(id, <случайное основание>)` завершается
    отказом, текст которого называет `mr-sync`. Все git-вызовы команды
    видны: `gitcmd.in_repo` — хуком песочницы, плотницкие вызовы —
    шпионом `subprocess.run` песочницы (`git_spy`); среди них нет ни
    `commit`, ни `commit-tree`, ни `update-ref`, ни `push`.
    `tests_locked_sha` задачи не изменился.

    Ловит мутацию: проверки состояния в `amend` нет — команда идёт своим
    обычным путём (рабочая копия, снимок планки) и отказывает иным текстом
    без mr-sync; проверка поставлена после сверки снимка планки или после
    коммита — раньше неё сработает отказ «нет изменений» без mr-sync либо
    в вызовах будет `commit`; отказ оставлен только точке отправки
    `gitcmd` — подсказки mr-sync в выводе команды нет.
    """
    rng = random.Random(seed)
    sandbox.set_state(STATE)
    locked_before = "".join(rng.choice("0123456789abcdef") for _ in range(40))
    store.update_task(store.db(), sandbox.TASK, tests_locked_sha=locked_before)
    seen = []

    def record(repo, *args):
        seen.append(list(args))
        return None

    sandbox.in_repo_handlers.append(record)
    spy_before = len(sandbox.git_spy.calls)
    out = run(amend.cmd_amend_tests, sandbox.TASK, words(rng))
    note = f"зерно: {seed}"
    assert "mr-sync" in out, f"{note}: подсказки mr-sync нет:\n{out}"
    calls = seen + [list(c) for c in sandbox.git_spy.calls[spy_before:]]
    for word in ("commit", "commit-tree", "update-ref", "push"):
        hits = [c for c in calls if word in c]
        assert hits == [], f"{note}: git {word} при отказе: {hits}"
    assert sandbox.task_row()["tests_locked_sha"] == locked_before, note
    assert sandbox.state() == STATE, note


def test_ac17_escalation_from_awaiting_human_returns_there(sandbox, seed):
    """Эскалация из `awaiting_human` после `approve` возвращает задачу в `awaiting_human`.

    Сценарий: задача песочницы эскалирована так, как это пишет точка
    эскалации: `state = escalated`, `escalated_from = awaiting_human`,
    запись журнала `state -> escalated` со случайной причиной (без метки
    «нужен шаг роли»). `fsm.cmd_approve(id)` снимает эскалацию: задача в
    `awaiting_human`, в журнале — переход `state -> awaiting_human`.

    Ловит мутацию: возврат из эскалации особым случаем ведёт не в
    `escalated_from`, а в `in_dev` (умолчание `or "in_dev"` применено к
    состояниям без роли) — задача окажется в `in_dev`.
    """
    rng = random.Random(seed)
    store.update_task(store.db(), sandbox.TASK, state="escalated",
                      escalated_from=STATE)
    store.journal(store.db(), sandbox.TASK, "fsm", "state -> escalated",
                  f"сдвиг ссылки документов: {words(rng)} m{rng.randrange(10 ** 9)}")
    rows_before = len(store.task_steps(store.db(), sandbox.TASK))
    out = run(fsm.cmd_approve, sandbox.TASK)
    note = f"зерно: {seed}"
    assert sandbox.state() == STATE, f"{note}: состояние {sandbox.state()}:\n{out}"
    new = [r["action"] for r in store.task_steps(store.db(), sandbox.TASK)[rows_before:]]
    assert f"state -> {STATE}" in new, f"{note}: {new}"

