"""Указание Оператора на гейте SPEC: `approve <id> --note <файл>` — запись журнала, раздел брифа test_author, часть пакета ревьювера, отказы флага до lease и под lease.

Группа: долгоживущий
Красен до реализации: ключа `--note` пульт не знает — значение флага уходит позиционным `sha` («sha '--note' короче минимальной длины»), `approve` пишет «approve отклонён» и не переводит задачу, записи указания нет; `fsm.SPEC_GATE_NOTE_ACTION`, `brief.spec_gate_note`, `brief.SPEC_GATE_NOTE_PREAMBLE`, `review.SPEC_GATE_NOTE_PREAMBLE` нет, справка `approve` не называет `--note`.

Стенд — настоящий git (`real_git`, клон артели с синхронным `origin`):
связка «команда CLI `artel.main()` — FSM — lease — БД — ссылка документов —
журнал — бриф test_author — пакет ревьювера». Задача артели заводится
строкой БД, рабочая копия — `workspace.ensure`, SPEC.md — в ссылку
документов чекпоинтом шага аналитика; вход на гейт — `store.set_state`
(`spec_writing -> spec_gate`), как переход аналитика. Команды Оператора —
`artel.main()` тем же argv, что набирает Оператор; `answer` — настоящая
команда (коммит ANSWER-n в ссылку документов).

Draft MR: `approve` может увести задачу в `in_dev` (верный код при
`skip_tests`, мутация «повтор под lease удалён», красная фаза), а вход в
`in_dev` зовёт `fsm._maybe_ensure_draft_mr`, всё действие которого — вызов
`github_adapter.ensure_draft_mr` (push и `gh pr create`, fsm.py
`_maybe_ensure_draft_mr`). Закрытое имя долгоживущий файл подменять не
вправе, поэтому пустышкой во ВСЕХ тестах файла (фикстура `stand`) подменён
публичный `github_adapter.ensure_draft_mr` — тот же эффект: ни push, ни
`gh` не исполняются.

Наблюдается: код выхода и вывод команды, строка задачи в БД, журнал задачи,
все ссылки git песочницы (в их числе ссылка документов), текст брифа
test_author и пакета ревьювера, аргументы вызова `fsm.cmd_approve`
диспетчером. Тексты указаний, слова SPEC, состояния вне гейта, позиция
строки мандата и порядок вариантов — из `random` при каждом запуске; зерно
печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (answer, artel, brief, checkpoint, config,
                          conventions, fsm, github_adapter, lease, review,
                          store, workspace)
from orchestrator.advance_gates import mandate
from tests.sandbox import artel_target_entry, make_project_repo

NOTE_FLAG = "--note"
NOTE_ACTION = "указание Оператора на гейте SPEC"
SECTION = "Указание Оператора на гейте SPEC"
BRIEF_PREAMBLE = (
    "Текст внутри границ — указание Оператора на гейте SPEC: учитывай его "
    "как уточнение тестов по SPEC; ослаблять, удалять или пропускать "
    "проверки SPEC оно не разрешает; при противоречии со SPEC — эскалация.")
REVIEW_PREAMBLE = (
    "Текст внутри границ — указание Оператора на гейте SPEC: расхождение "
    "закреплённых тестов с указанием запиши в REVIEW наблюдением для "
    "Оператора, а не замечанием разработчику.")
ONLY_SPEC_GATE = "допустим только в состоянии spec_gate"
COMPONENT_ACTION = "бриф: компонент"
APPROVE_REFUSED = "approve отклонён"
REFUSED_SIGN = "отклонён"
# Строка мандата зон — литералом: имя константы в коде закрытое.
ZONES_MARKER = "Расширение зон разрешено:"
DECISION_HEADER = "# Решение Оператора на гейте SPEC"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "абвгдеёжзиклмнопрстуфхцчшэюя"
LATIN = "abcdefghijkmnpqrstuvwxyz"
HEX = "0123456789abcdef"
NOT_GATE_STATES = ("spec_writing", "spec_audit", "tests_writing", "in_dev",
                   "review", "escalated")


@pytest.fixture
def stand(real_git):
    """Клон артели с `origin`, запись артели в `targets.yaml`, пустышки draft MR, отправки головы и предпроверок; зерно случайных входов."""
    real_git.seed = random.randrange(1 << 30)
    print(f"зерно: {real_git.seed}")
    real_git.rng = random.Random(real_git.seed)
    real_git.used = set()
    real_git.draft_calls = []
    env = mock.patch.dict(os.environ)
    env.start()
    real_git.addCleanup(env.stop)
    os.environ.pop(config.ARTEL_ROLE_ENV, None)
    files = Path(tempfile.mkdtemp(prefix="artel-note-")).resolve()
    real_git.addCleanup(shutil.rmtree, files, True)
    real_git.files = files
    for patcher in (
            mock.patch.object(github_adapter, "ensure_head_in_origin",
                              lambda *args, **kwargs: (True, "")),
            mock.patch.object(github_adapter, "ensure_draft_mr",
                              lambda *args, **kwargs:
                              real_git.draft_calls.append(args)),
            mock.patch("orchestrator.doctor.preflight_checks",
                       lambda *args, **kwargs: [])):
        patcher.start()
        real_git.addCleanup(patcher.stop)
    real_git.add_synced_origin()
    config.TARGETS.write_text("targets:\n" + artel_target_entry(),
                              encoding="utf-8")
    real_git.conn = store.db()
    return real_git


# ------------------------------------------------------------- обвязка


def word(stand, size: int = 6, alphabet: str = LETTERS) -> str:
    while True:
        text = "".join(stand.rng.choice(alphabet) for _ in range(size))
        if text not in stand.used:
            stand.used.add(text)
            return text


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def ulid(stand) -> str:
    return "01" + "".join(stand.rng.choice(CROCKFORD) for _ in range(24))


def note_text(stand) -> str:
    """Случайный многострочный текст указания без строк мандатов, с уникальной меткой."""
    lines = [" ".join(word(stand, stand.rng.randint(3, 8))
                      for _ in range(stand.rng.randint(3, 9)))
             for _ in range(stand.rng.randint(1, 4))]
    lines[0] = f"Метка {word(stand, 10)}: {lines[0]}"
    return "\n".join(lines) + "\n"


def sized_text(stand, size: int, crlf: bool = False) -> bytes:
    """Байты файла указания ровно `size` байт: кириллица (по два байта на букву), переводы строк `\\n` либо `\\r\\n`, хвост — латиница."""
    newline = "\r\n" if crlf else "\n"
    text = f"Метка {word(stand, 10)}{newline}"
    line_size = 0
    while len(text.encode("utf-8")) + line_size + 64 < size:
        line = " ".join("".join(stand.rng.choice(LETTERS) for _ in range(6))
                        for _ in range(8)) + newline
        line_size = len(line.encode("utf-8"))
        text += line
    data = text.encode("utf-8")
    return data + b"z" * (size - len(data))


def spec_text(stand, task_id: str, kind: str = "plain") -> str:
    """SPEC задачи: `plain` — AC-разметка без деления; `division` — с делением на две части; `skip` — с `skip_tests`; `legacy` — `schema_version: 1` без AC-разметки; `protected` — в `zones` защищённый путь `skills/…` (мягкий отказ `approve`)."""
    zone = f"orchestrator/fx_{word(stand, alphabet=LATIN)}.py"
    if kind == "protected":
        zone += f", skills/fx_{word(stand, alphabet=LATIN)}.md"
    schema = 1 if kind == "legacy" else 5
    skip = f"skip_tests: {word(stand)} {word(stand)}\n" if kind == "skip" else ""
    criteria = "\n\n".join(f"AC-{n}. Критерий {word(stand)} номер {n}."
                           for n in range(1, stand.rng.randint(2, 4)))
    division = ""
    if kind == "division":
        parts = [f"Часть {word(stand)}" for _ in range(2)]
        orders = ("первая, без зависимостей", "после части 1")
        division = ("## Оценка объёма и деление\nФикстура.\n\n## Деление\n\n"
                    + "".join(
                        f"### {title}\n\nЗоны: orchestrator/fx_"
                        f"{word(stand, alphabet=LATIN)}.py\nПорядок: {order}"
                        f"\n\nТекст ТЗ части «{title}».\n\n"
                        for title, order in zip(parts, orders)))
    return (f"---\ntask: {task_id}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: {schema}\nzones: {zone}\n"
            f"budget_usd: 30\n{skip}---\n\n# SPEC: фикстура {word(stand)}\n\n"
            f"## Контекст\n\nФикстура {word(stand)}.\n\n## Требования\n\n"
            f"1. Требование {word(stand)}.\n\n## Критерии приёмки\n\n"
            f"{criteria}\n\n{division}## Не входит\n\nНичего.\n")


def put_doc(stand, t, name: str, text: str) -> None:
    """Документ задачи — в ссылку документов чекпоинтом шага и копией на дисковом пути чтения; фиксация головы."""
    t.docs.mkdir(parents=True, exist_ok=True)
    (t.docs / name).write_text(text, encoding="utf-8")
    checkpoint.commit_step_artifacts(stand.conn, t.id, "analyst")
    store.record_fixation(stand.conn, t.id)
    t.docs.mkdir(parents=True, exist_ok=True)
    (t.docs / name).write_text(text, encoding="utf-8")
    disk = config.TASKS / t.id
    disk.mkdir(parents=True, exist_ok=True)
    (disk / name).write_text(text, encoding="utf-8")


def new_task(stand, kind: str = "plain") -> SimpleNamespace:
    """Задача артели на `spec_gate`: рабочая копия, SPEC вида `kind` в ссылке документов, вход на гейт записью `state -> spec_gate`."""
    tid = ulid(stand)
    branch = f"task/{tid.lower()}-{word(stand, alphabet=LATIN)}"
    title = f"Указание {word(stand)}"
    store.insert_task(stand.conn, tid, title, "spec_writing", branch,
                      config.DEFAULT_TARGET, 25.0)
    _wt, error = workspace.ensure(tid, branch)
    assert error is None, note(stand, f"рабочая копия не заведена: {error}")
    t = SimpleNamespace(id=tid, branch=branch, title=title,
                        docs=config.PROJECTS / config.DEFAULT_TARGET
                        / "tasks" / tid)
    put_doc(stand, t, "SPEC.md", spec_text(stand, tid, kind))
    store.set_state(stand.conn, tid, "spec_gate", "analyst",
                    expected_state="spec_writing",
                    detail=f"SPEC готов {word(stand)}")
    store.record_fixation(stand.conn, tid)
    return t


def back_to_gate(stand, t) -> None:
    """Новый круг аналитика: `state -> spec_writing`, новый SPEC, `state -> spec_gate`."""
    store.set_state(stand.conn, t.id, "spec_writing", "operator",
                    expected_state=state(stand, t),
                    detail=f"возврат {word(stand)}")
    put_doc(stand, t, "SPEC.md", spec_text(stand, t.id))
    store.set_state(stand.conn, t.id, "spec_gate", "analyst",
                    expected_state="spec_writing",
                    detail=f"SPEC переписан {word(stand)}")
    store.record_fixation(stand.conn, t.id)


def write_file(stand, data) -> str:
    path = stand.files / f"note-{word(stand, alphabet=LATIN)}.md"
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return str(path)


def cli(*argv: str) -> tuple[bool, str]:
    """(успех, stdout + stderr + текст выхода) команды `artel.py <argv>`."""
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


def approve_note(stand, t, data) -> tuple[bool, str]:
    return cli("approve", t.id, NOTE_FLAG, write_file(stand, data))


def approve_plain(stand, t) -> tuple[bool, str]:
    return cli("approve", t.id)


def state(stand, t) -> str:
    return store.get_task(stand.conn, t.id)["state"]


def rows(stand, t) -> list:
    return list(store.task_steps(stand.conn, t.id))


def journal(stand, t) -> str:
    return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                     for r in rows(stand, t))


def note_rows(stand, t) -> list:
    return [r for r in rows(stand, t) if r["action"] == NOTE_ACTION]


def snapshot(stand, t) -> tuple:
    """(строка задачи, журнал задачи, все ссылки git песочницы)."""
    row = dict(store.get_task(stand.conn, t.id))
    steps = [tuple(r) for r in rows(stand, t)]
    refs = stand.git("for-each-ref", "--format=%(refname) %(objectname)")
    return row, steps, refs


def assert_unchanged(stand, t, before: tuple, out: str) -> None:
    """Отказ назван в выводе; строка задачи, журнал и ссылки git — прежние."""
    why = note(stand, f"вывод:\n{out}\nжурнал:\n{journal(stand, t)}")
    assert REFUSED_SIGN in out, why
    after = snapshot(stand, t)
    assert after[0]["state"] == before[0]["state"], why
    assert after[0] == before[0], why
    assert after[1] == before[1], why
    assert after[2] == before[2], why


def escalate_and_answer(stand, t) -> tuple[str, str]:
    """Эскалация test_author из `tests_writing`, ответ Оператора `answer`, снятие эскалации `approve` — задача снова в `tests_writing`; (текст эскалации, текст ответа)."""
    question = f"Вопрос эскалации {word(stand, 10)}"
    store.update_task(stand.conn, t.id, escalated_from="tests_writing",
                      answer_baseline=0)
    store.set_state(stand.conn, t.id, "escalated", "test_author",
                    expected_state="tests_writing", detail=question)
    reply = f"Ответ Оператора {word(stand, 10)} {word(stand)}\n"
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            answer.cmd_answer(t.id, write_file(stand, reply))
        except SystemExit as exc:
            out.write(f"\n{exc.code}")
    _ok, text = approve_plain(stand, t)
    assert state(stand, t) == "tests_writing", note(
        stand, f"предпосылка: возврат из эскалации:\n{out.getvalue()}\n"
        f"{text}\n{journal(stand, t)}")
    return question, reply.strip()


def role_brief(stand, t) -> str:
    return brief.test_author_answer_component(stand.conn, t.id) or ""


def package(stand, t) -> dict:
    return review.review_package(stand.conn, t.id, t.title, t.branch)


def review_ready(stand, t) -> None:
    store.update_task(stand.conn, t.id, state="review")


def boundary_parts() -> tuple[str, str]:
    """(начало, конец) граничной обёртки — по самой `brief.wrap_boundary`, без идентификатора запуска."""
    sample = brief.wrap_boundary("RUNID", "ТЕЛО")
    head, _, tail = sample.partition("ТЕЛО")
    return head.split("RUNID")[0].strip(), tail.split("RUNID")[0].strip()


def assert_wrapped_after(text: str, preamble: str, body: str, why: str) -> int:
    """Строка `preamble`, за ней открывающий граничный маркер, внутри — `body`, затем закрывающий маркер; индекс `preamble`."""
    opening, closing = boundary_parts()
    at = text.find(preamble)
    assert at >= 0, why
    opened = text.find(opening, at + len(preamble))
    assert opened >= 0, why
    body_at = text.find(body.strip(), opened)
    assert body_at >= 0, why
    assert text.find(closing, opened) > body_at, why
    assert body.strip() not in text[at + len(preamble):opened], why
    return at


def section_label(text: str) -> str:
    """Текст заголовка `### …` раздела указания в брифе."""
    at = text.find(f"### {SECTION}")
    return text[at + 4:text.find("\n", at)].strip()


def components(stand, t, actor: str) -> list:
    return [r["detail"] or "" for r in rows(stand, t)
            if r["action"] == COMPONENT_ACTION and r["actor"] == actor]


# ---------------------------------------------------------------- AC-1


def test_ac1_note_moves_to_tests_writing_and_journals_note(stand):
    """`approve <id> --note f` на `spec_gate`: задача в `tests_writing`, одна запись `operator` действия указания с полным текстом файла; константа действия — новая, не `state -> `.

    Сценарий: задача артели на гейте SPEC с AC-разметкой без деления и без
    `skip_tests`, файл указания — случайный многострочный текст с
    завершающим переводом строки. После команды — `tests_writing`, ровно
    одна запись действия `fsm.SPEC_GATE_NOTE_ACTION` от `operator`, её
    деталь равна тексту файла байт в байт. Значение константы — ровно
    «указание Оператора на гейте SPEC»; ни одна другая публичная константа
    `*_ACTION` загруженных модулей `orchestrator` и ни одно прежнее действие
    журнала его не повторяют; `state -> ` оно не начинается.

    Ловит мутацию: `--note` уходит позиционным sha — отказ «sha короче
    минимальной длины», перехода и записи нет; запись пишется исполнителем
    `fsm`; деталь — текст после `strip()` или первая строка (теряется хвост
    файла); действие названо прежним «указание Оператора» (совпадение с
    действием `answer`).
    """
    t = new_task(stand)
    text = note_text(stand)

    ok, out = approve_note(stand, t, text)

    why = note(stand, f"вывод:\n{out}\nжурнал:\n{journal(stand, t)}")
    assert ok, why
    assert state(stand, t) == "tests_writing", why
    found = note_rows(stand, t)
    assert len(found) == 1, why
    assert found[0]["actor"] == "operator", why
    assert found[0]["detail"] == text, why
    assert fsm.SPEC_GATE_NOTE_ACTION == NOTE_ACTION, why
    assert not fsm.SPEC_GATE_NOTE_ACTION.startswith("state -> "), why
    clashes = sorted(
        f"{name}.{attr}" for name, module in list(sys.modules.items())
        if name.split(".")[0] == "orchestrator" and module is not None
        for attr, value in list(vars(module).items())
        if attr.endswith("_ACTION") and not attr.startswith("_")
        and isinstance(value, str) and value == NOTE_ACTION
        and attr != "SPEC_GATE_NOTE_ACTION")
    assert clashes == [], note(stand, f"действие указания совпало с {clashes}")
    for prior in ("указание Оператора", APPROVE_REFUSED, COMPONENT_ACTION,
                  "ANSWER создан, ждёт approve", "state -> tests_writing"):
        assert prior != NOTE_ACTION, why


# ---------------------------------------------------------------- AC-2


def test_ac2_brief_section_after_return_reason_and_answer(stand):
    """После `approve --note`, эскалации и ответа бриф test_author несёт раздел указания с преамбулой перед границей — после причины возврата и ANSWER, с записью «бриф: компонент».

    Сценарий: `approve --note` уводит задачу в `tests_writing`; test_author
    эскалирует, Оператор отвечает `answer`, `approve` возвращает задачу в
    `tests_writing` (без нового `state -> spec_gate`). `brief.spec_gate_note`
    отдаёт текст файла; в брифе (`brief.test_author_answer_component`) —
    заголовок раздела «Указание Оператора на гейте SPEC», за ним строка
    `brief.SPEC_GATE_NOTE_PREAMBLE` (текст требования 6) перед открывающим
    граничным маркером, внутри границы — текст указания; раздел стоит после
    текста причины возврата (вопроса эскалации) и после текста ANSWER; сборка
    брифа добавляет запись «бриф: компонент» test_author с меткой раздела.

    Ловит мутацию: раздел вставлен первым куском брифа (до причины
    возврата) или перед ANSWER; преамбула внутри границы, а не перед ней;
    раздел собран мимо `_journal_component` — записи «бриф: компонент» с
    меткой раздела нет; текст преамбулы перефразирован.
    """
    t = new_task(stand)
    text = note_text(stand)
    _ok, out = approve_note(stand, t, text)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    question, reply = escalate_and_answer(stand, t)
    before = len(components(stand, t, "test_author"))

    got = brief.spec_gate_note(stand.conn, t.id)
    text_of_brief = role_brief(stand, t)

    why = note(stand, f"бриф:\n{text_of_brief}\nжурнал:\n{journal(stand, t)}")
    assert got == text, why
    assert brief.SPEC_GATE_NOTE_PREAMBLE == BRIEF_PREAMBLE, why
    section_at = text_of_brief.find(f"### {SECTION}")
    assert section_at >= 0, why
    at = assert_wrapped_after(text_of_brief, BRIEF_PREAMBLE, text, why)
    assert section_at < at, why
    assert 0 <= text_of_brief.find(question) < section_at, why
    assert 0 <= text_of_brief.find(reply) < section_at, why
    label = section_label(text_of_brief)
    added = components(stand, t, "test_author")[before:]
    assert any(d.startswith(f"{label}: ") for d in added), why


def external_task_with_note(stand) -> tuple:
    """Задача внешнего проекта в `tests_writing` после гейта SPEC с записью указания `operator` после `state -> spec_gate` (так её оставляет `approve --note`); (задача, текст указания)."""
    name = f"p{word(stand, alphabet=LATIN)}"
    make_project_repo(name)
    tid = ulid(stand)
    branch = f"task/{tid.lower()}-{word(stand, alphabet=LATIN)}"
    title = f"Внешняя {word(stand)}"
    store.insert_task(stand.conn, tid, title, "spec_writing", branch, name, 25.0)
    t = SimpleNamespace(id=tid, branch=branch, title=title,
                        docs=config.PROJECTS / name / "tasks" / tid)
    put_doc(stand, t, "SPEC.md", spec_text(stand, tid))
    store.set_state(stand.conn, tid, "spec_gate", "analyst",
                    expected_state="spec_writing", detail="SPEC готов")
    text = note_text(stand)
    store.set_state(stand.conn, tid, "tests_writing", "operator",
                    expected_state="spec_gate", detail="SPEC одобрен")
    store.journal(stand.conn, tid, "operator", NOTE_ACTION, text)
    return t, text


def test_ac2_brief_section_alone_and_before_project_conventions(stand):
    """Без эскалации бриф test_author задачи артели всё равно несёт раздел указания; у задачи внешнего проекта раздел стоит до конвенций проекта.

    Сценарий: (1) задача артели — `approve --note` и сразу бриф: причины
    возврата и ANSWER нет, бриф не `None`, в нём раздел с преамбулой перед
    границей и запись «бриф: компонент» с меткой раздела; (2) задача
    внешнего проекта в `tests_writing` с записью указания `operator` после
    `state -> spec_gate`: раздел указания (с его текстом) — раньше
    компонента конвенций проекта (`conventions.md` либо пометки «не
    разобраны»/«не прочитаны»).

    Ловит мутацию: раздел добавляется только вместе с ANSWER (условие на
    соседний компонент) — бриф артели `None`; раздел приклеен после
    конвенций, в конец кусков перед справочником ядра.
    """
    t = new_task(stand)
    text = note_text(stand)
    _ok, out = approve_note(stand, t, text)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    before = len(components(stand, t, "test_author"))

    artel_brief = role_brief(stand, t)

    why = note(stand, f"бриф артели:\n{artel_brief}")
    assert f"### {SECTION}" in artel_brief, why
    assert_wrapped_after(artel_brief, BRIEF_PREAMBLE, text, why)
    label = section_label(artel_brief)
    added = components(stand, t, "test_author")[before:]
    assert any(d.startswith(f"{label}: ") for d in added), why

    ext, ext_text = external_task_with_note(stand)
    ext_brief = role_brief(stand, ext)

    why = note(stand, f"бриф внешнего проекта:\n{ext_brief}")
    section_at = ext_brief.find(f"### {SECTION}")
    assert section_at >= 0, why
    marks = [ext_brief.find(m) for m in (
        f"### {conventions.FILE_NAME}", brief.PROJECT_CONVENTIONS_UNPARSED_MARK,
        brief.PROJECT_CONVENTIONS_UNREAD_MARK)]
    marks = [m for m in marks if m >= 0]
    assert marks, note(stand, f"предпосылка: конвенций в брифе нет:\n{ext_brief}")
    assert section_at < min(marks), why
    assert ext_text.strip() in ext_brief[section_at:min(marks)], why


# ---------------------------------------------------------------- AC-3


def test_ac3_review_package_part_right_after_answers(stand):
    """Пакет ревьювера после `approve --note`: часть с преамбулой перед границей и текстом указания — сразу за ANSWER-n, до списка файлов; ключи пакета прежние, запись «бриф: компонент» от reviewer.

    Сценарий: две задачи артели с одинаковой историей — гейт SPEC,
    эскалация test_author, `answer`, возврат в `tests_writing`, `review`;
    первая одобрена с `--note`, вторая без. Пакет первой несёт
    `review.SPEC_GATE_NOTE_PREAMBLE` (текст требования 7) перед открывающим
    граничным маркером, внутри — текст указания; между текстом ANSWER-1 и
    преамбулой — не больше одного заголовка части (своего), и он не о
    ANSWER; часть раньше «Изменённые файлы». Набор ключей словаря — как у
    второй задачи; сборка пакета первой задачи пишет на одну запись «бриф:
    компонент» от reviewer больше, чем сборка второй. Пакет второй задачи
    преамбулы не несёт.

    Ловит мутацию: часть добавлена после цикла долгоживущих файлов/diff или
    перед ANSWER; указание отдано отдельным ключом словаря пакета; запись
    reviewer не пишется; часть (пустая) есть и без указания; для пакета
    взята преамбула брифа test_author.
    """
    t = new_task(stand)
    twin = new_task(stand)
    text = note_text(stand)
    _ok, out = approve_note(stand, t, text)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    _ok, out = approve_plain(stand, twin)
    assert state(stand, twin) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    _q, reply = escalate_and_answer(stand, t)
    escalate_and_answer(stand, twin)
    review_ready(stand, t)
    review_ready(stand, twin)
    before = len(components(stand, t, "reviewer"))
    twin_before = len(components(stand, twin, "reviewer"))

    got = package(stand, t)
    plain = package(stand, twin)

    body = got["text"]
    why = note(stand, f"пакет:\n{body}")
    assert review.SPEC_GATE_NOTE_PREAMBLE == REVIEW_PREAMBLE, why
    at = assert_wrapped_after(body, REVIEW_PREAMBLE, text, why)
    reply_at = body.rfind(reply, 0, at)
    assert reply_at >= 0, why
    headers = re.findall(r"^### .*$", body[reply_at:at], re.M)
    assert len(headers) <= 1, why
    assert all("ANSWER" not in h for h in headers), why
    assert body.find("### Изменённые файлы") > body.find(text.strip(), at), why
    assert set(got) == set(plain), why
    assert REVIEW_PREAMBLE not in plain["text"], note(stand, plain["text"])
    added = len(components(stand, t, "reviewer")) - before
    twin_added = len(components(stand, twin, "reviewer")) - twin_before
    assert added == twin_added + 1, note(stand, journal(stand, t))


# ---------------------------------------------------------------- AC-4


def test_ac4_note_outside_spec_gate_refused(stand):
    """`approve --note f` вне `spec_gate` (каждое из шести состояний в случайном порядке) — отказ «допустим только в состоянии spec_gate»; строка задачи, журнал и ссылки прежние.

    Ловит мутацию: проверка состояния только под lease — запись «lease
    взят» в журнале; проверки состояния нет — в `escalated`/`in_dev` идёт
    прежний `approve` (запись «approve отклонён»/смена состояния); текст
    отказа без «допустим только в состоянии spec_gate».
    """
    t = new_task(stand)
    order = list(NOT_GATE_STATES)
    stand.rng.shuffle(order)
    for current in order:
        store.update_task(stand.conn, t.id, state=current)
        before = snapshot(stand, t)

        _ok, out = approve_note(stand, t, note_text(stand))

        why = note(stand, f"{current}: вывод:\n{out}")
        assert ONLY_SPEC_GATE in out, why
        assert_unchanged(stand, t, before, out)


# ---------------------------------------------------------------- AC-5


def test_ac5_bad_note_values_refused(stand):
    """`--note` без значения, со значением `--…`, с несуществующим, нечитаемым (каталог, не UTF-8), пустым и пробельным файлом — отказ; строка задачи, журнал и ссылки прежние.

    Сценарий: задача на `spec_gate`, варианты перебираются в случайном
    порядке на одной задаче; перед каждым — снимок, после — сверка.

    Ловит мутацию: пустота проверяется `== ""` без `strip()` — файл из
    пробелов и переводов строк принят (переход в `tests_writing`);
    `UnicodeDecodeError` не перехвачен — трассировка вместо отказа; значение
    `--fresh-suite` взято за путь файла; `--note` без значения уходит
    позиционным sha (запись «approve отклонён» в журнале).
    """
    t = new_task(stand)
    folder = stand.files / f"dir-{word(stand, alphabet=LATIN)}"
    folder.mkdir()
    flag_value = stand.rng.choice(
        ("--fresh-suite", "--no-answer", f"--{word(stand, alphabet=LATIN)}"))
    variants = [
        ("без значения", [NOTE_FLAG]),
        ("значение --", [NOTE_FLAG, flag_value]),
        ("нет файла", [NOTE_FLAG, str(stand.files / f"{word(stand, alphabet=LATIN)}.md")]),
        ("каталог", [NOTE_FLAG, str(folder)]),
        ("не UTF-8", [NOTE_FLAG, write_file(stand, b"\xff\xfe\xfa " + word(stand).encode("utf-8"))]),
        ("пустой", [NOTE_FLAG, write_file(stand, "")]),
        ("пробелы", [NOTE_FLAG, write_file(stand, stand.rng.choice(
            (" \n\t\n", "\n\n", "   ", "\r\n \r\n")))]),
    ]
    stand.rng.shuffle(variants)
    for name, tail in variants:
        before = snapshot(stand, t)
        try:
            _ok, out = cli("approve", t.id, *tail)
        except Exception as exc:  # отказ обязан быть текстом, не трассировкой
            pytest.fail(note(stand, f"{name}: исключение {exc!r}"))
        assert_unchanged(stand, t, before, f"[{name}]\n{out}")


# ---------------------------------------------------------------- AC-6


ANSWER_HINT = r"answer (?:{tid}|<id>) \S"


@pytest.mark.parametrize("marker_kind", ["weakening", "test_id", "zones",
                                         "merge_after"])
def test_ac6_mandate_line_in_note_refused_with_hint(stand, marker_kind):
    """Файл указания со строкой мандата — отказ; для мандатов тестов причина называет `answer <id> <файл>`, для зон и зависимостей мержа — поля SPEC и возврат `reject`; строка задачи, журнал и ссылки прежние.

    Сценарий: строка маркера вида `marker_kind` (с элементом, иногда с
    отступом) вставлена в случайное место многострочного указания.

    Ловит мутацию: проверяется только первая строка файла; перебираются
    два маркера тестов без зон и зависимостей мержа; маркер с отступом не
    распознан (нет `strip()` — это делает `mandate.line_elements`); одна
    подсказка `answer` для всех маркеров — у зон причина без `reject`.
    """
    t = new_task(stand)
    line = {
        "weakening": f"{mandate.TEST_WEAKENING_MANDATE_MARKER} tests/test_fx_{word(stand, alphabet=LATIN)}.py",
        "test_id": f"{mandate.TEST_ID_MANDATE_MARKER} default > {word(stand)} {word(stand)}",
        "zones": f"{ZONES_MARKER} orchestrator/fx_{word(stand, alphabet=LATIN)}.py",
        "merge_after": f"{mandate.MERGE_AFTER_MANDATE_MARKER} нет",
    }[marker_kind]
    assert mandate.line_elements(line, line.split(":")[0] + ":") is not None, note(
        stand, f"предпосылка: строка не мандат: {line}")
    lines = note_text(stand).splitlines()
    lines.insert(stand.rng.randrange(len(lines) + 1),
                 stand.rng.choice(("", "  ")) + line)
    before = snapshot(stand, t)

    _ok, out = approve_note(stand, t, "\n".join(lines) + "\n")

    assert_unchanged(stand, t, before, out)
    hint = re.search(ANSWER_HINT.format(tid=re.escape(t.id)), out)
    why = note(stand, f"{marker_kind}: вывод:\n{out}")
    if marker_kind in ("weakening", "test_id"):
        assert hint, why
    else:
        assert "reject" in out, why
        assert "SPEC" in out, why
        assert not hint, why


def test_ac6_decision_header_note_refused(stand):
    """Файл указания, начинающийся заголовком файла решения (возможно после пустых строк), — отказ; строка задачи, журнал и ссылки прежние.

    Ловит мутацию: заголовок ищется только на первой строке (`text.startswith`) — файл с ведущей пустой строкой принят; проверки заголовка нет — файл решения принят указанием.
    """
    t = new_task(stand)
    text = (stand.rng.choice(("", "\n", "\n  \n")) + DECISION_HEADER
            + "\n\n" + note_text(stand))
    before = snapshot(stand, t)

    _ok, out = approve_note(stand, t, text)

    assert_unchanged(stand, t, before, out)


# ---------------------------------------------------------------- AC-7


def test_ac7_size_limit_by_file_bytes(stand):
    """Файл ровно `config.CONTEXT_FILE_MAX_BYTES` байт принят (переход и запись, как в AC-1); на байт больше — отказ, строка задачи, журнал и ссылки прежние.

    Сценарий: оба файла — кириллица (два байта на букву); файл сверх
    предела — с переводами строк `\\r\\n`, так что и число символов
    прочитанного текста, и длина его UTF-8 после `read_text` (CRLF -> LF)
    меньше предела — различает только размер файла в байтах.

    Ловит мутацию: предел сравнивается с `len(text)` или с
    `len(text.encode())` прочитанного текста — файл сверх предела принят;
    сравнение `>=` вместо `>` — файл ровно на пределе отклонён.
    """
    limit = config.CONTEXT_FILE_MAX_BYTES
    exact = sized_text(stand, limit)
    over = sized_text(stand, limit + 1, crlf=True)
    assert len(exact) == limit and len(over) == limit + 1, note(stand, "предпосылка размеров")
    big = new_task(stand)
    before = snapshot(stand, big)

    _ok, out = approve_note(stand, big, over)

    assert_unchanged(stand, big, before, out)

    t = new_task(stand)
    ok, out = approve_note(stand, t, exact)

    why = note(stand, f"вывод:\n{out[-2000:]}")
    assert ok, why
    assert state(stand, t) == "tests_writing", why
    found = note_rows(stand, t)
    assert [r["actor"] for r in found] == ["operator"], why
    assert found[0]["detail"] == exact.decode("utf-8"), why


# ---------------------------------------------------------------- AC-8


@pytest.mark.parametrize("kind", ["division", "skip", "legacy"])
def test_ac8_note_refused_when_approve_leads_past_tests_writing(stand, kind):
    """`--note` при SPEC с делением, с `skip_tests` и без AC-разметки — отказ; строка задачи, журнал и ссылки прежние.

    Ловит мутацию: проверка пути только по `skip_tests` — деление и
    `schema_version: 1` проходят (части заведены / переход в `in_dev`);
    проверка `requires_ac_markup` пропущена — SPEC без разметки уходит в
    `in_dev`; проверка под lease вместо до lease — запись «lease взят».
    """
    t = new_task(stand, kind)
    before = snapshot(stand, t)

    _ok, out = approve_note(stand, t, note_text(stand))

    assert_unchanged(stand, t, before, out)


def test_ac8_soft_refusal_with_note_journals_same_refusal_only(stand):
    """Мягкий отказ `approve` (защищённый путь в `zones`) с `--note` пишет ту же запись «approve отклонён», что и без `--note`, а записи указания нет.

    Сценарий: задача на `spec_gate`, `zones` SPEC несёт путь `skills/…` —
    `approve` без флага журналирует «approve отклонён» и
    оставляет задачу на гейте. Затем `approve --note` на той же задаче:
    задача на гейте, новые записи «approve отклонён» те же (исполнитель и
    деталь), записи указания нет.

    Ловит мутацию: запись указания делается до сверок обработчика (сразу
    под lease) — после мягкого отказа запись указания остаётся; отказ с
    `--note` пишет иную деталь (с текстом указания).
    """
    t = new_task(stand, "protected")
    count = len(rows(stand, t))
    _ok, plain_out = approve_plain(stand, t)
    plain = [(r["actor"], r["detail"]) for r in rows(stand, t)[count:]
             if r["action"] == APPROVE_REFUSED]
    assert state(stand, t) == "spec_gate" and plain, note(
        stand, f"предпосылка: мягкий отказ без --note:\n{plain_out}")
    count = len(rows(stand, t))

    _ok, out = approve_note(stand, t, note_text(stand))

    why = note(stand, f"вывод:\n{out}\nжурнал:\n{journal(stand, t)}")
    assert state(stand, t) == "spec_gate", why
    with_note = [(r["actor"], r["detail"]) for r in rows(stand, t)[count:]
                 if r["action"] == APPROVE_REFUSED]
    assert with_note == plain, why
    assert note_rows(stand, t) == [], why


# ---------------------------------------------------------------- AC-9


@pytest.mark.parametrize("failure", ["CasConflict", "DocsRefIncident"])
def test_ac9_no_note_record_when_transition_fails(stand, failure):
    """`store.set_state` в `tests_writing` бросает `CasConflict`/`DocsRefIncident` — записи указания в журнале нет.

    Сценарий: подмена `store.set_state` бросает исключение на переходе в
    `tests_writing` (прочие переходы — настоящие); `approve --note` на
    гейте. Попытка перехода в `tests_writing` была, записи указания нет.

    Ловит мутацию: запись указания делается до `set_state` (или в
    `finally`) — запись есть при проигранном переходе.
    """
    t = new_task(stand)
    real = store.set_state
    attempts = []

    def failing(conn, task_id, new_state, *args, **kwargs):
        if new_state == "tests_writing":
            attempts.append(task_id)
            if failure == "CasConflict":
                raise store.CasConflict(task_id, "spec_gate", "in_dev")
            raise store.DocsRefIncident(f"инцидент {word(stand)}")
        return real(conn, task_id, new_state, *args, **kwargs)

    with mock.patch.object(store, "set_state", failing):
        try:
            _ok, out = approve_note(stand, t, note_text(stand))
        except store.CasConflict as exc:
            out = str(exc)

    why = note(stand, f"{failure}: вывод:\n{out}\nжурнал:\n{journal(stand, t)}")
    assert attempts == [t.id], why
    assert note_rows(stand, t) == [], why


# ---------------------------------------------------------------- AC-10


def test_ac10_note_does_not_take_sha_position(stand):
    """`approve <id> --note f [sha]` передаёт `fsm.cmd_approve` тот же sha, что `approve <id> [sha]`.

    Сценарий: `fsm.cmd_approve` подменён записью аргументов; диспетчер
    `artel.main()` разбирает пары argv без sha и со случайным sha (до и
    после пары `--note f`).

    Ловит мутацию: `--note`/его значение не исключены из
    `_approve_sha_arg` — sha становится «--note» или путём файла; sha после
    `--note f` пропущен.
    """
    t = new_task(stand)
    path = write_file(stand, note_text(stand))
    sha = "".join(stand.rng.choice(HEX) for _ in range(stand.rng.choice((8, 12, 40))))
    calls = []

    def record(*args, **kwargs):
        calls.append(args[1] if len(args) > 1 else kwargs.get("sha"))

    pairs = [((t.id,), (t.id, NOTE_FLAG, path)),
             ((t.id, sha), (t.id, NOTE_FLAG, path, sha)),
             ((t.id, sha), (t.id, sha, NOTE_FLAG, path))]
    with mock.patch.object(fsm, "cmd_approve", record):
        for plain, with_note in pairs:
            calls.clear()
            cli("approve", *plain)
            cli("approve", *with_note)
            why = note(stand, f"{plain} / {with_note}: {calls}")
            assert len(calls) == 2, why
            assert calls[0] == calls[1], why
            assert calls[0] == (plain[1] if len(plain) > 1 else None), why


# ---------------------------------------------------------------- AC-11


def test_ac11_note_lives_one_gate_pass(stand):
    """Новый проход `spec_gate`: `approve` без `--note` — указания нет ни в функции, ни в брифе, ни в пакете; с `--note` — новый текст; возврат через эскалацию указание сохраняет.

    Сценарий: `approve --note` (текст 1) -> возврат на гейт -> `approve`
    без флага: `brief.spec_gate_note` — `None`, в брифе test_author нет
    раздела, преамбулы и текста 1, в пакете ревьювера нет преамбулы и
    текста 1. Возврат на гейт -> `approve --note` (текст 2): функция и
    бриф несут текст 2, не текст 1. Эскалация из `tests_writing` и возврат
    без нового `state -> spec_gate`: функция по-прежнему — текст 2; пакет
    ревьювера несёт текст 2 с преамбулой, не текст 1.

    Ловит мутацию: функция берёт последнюю запись действия без границы
    `state -> spec_gate` — текст 1 переживает новый проход; граница — по
    любой записи `state -> …` (в том числе `state -> escalated`/`state ->
    tests_writing`) — указание теряется после эскалации; берётся первая
    запись, а не последняя после границы.
    """
    t = new_task(stand)
    first = note_text(stand)
    _ok, out = approve_note(stand, t, first)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    back_to_gate(stand, t)
    _ok, out = approve_plain(stand, t)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")

    gone = brief.spec_gate_note(stand.conn, t.id)
    gone_brief = role_brief(stand, t)
    review_ready(stand, t)
    gone_package = package(stand, t)["text"]

    why = note(stand, f"бриф:\n{gone_brief}\nпакет:\n{gone_package}")
    assert gone is None, why
    assert f"### {SECTION}" not in gone_brief, why
    assert BRIEF_PREAMBLE not in gone_brief, why
    assert first.strip() not in gone_brief, why
    assert REVIEW_PREAMBLE not in gone_package, why
    assert first.strip() not in gone_package, why

    back_to_gate(stand, t)
    second = note_text(stand)
    _ok, out = approve_note(stand, t, second)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")

    fresh_brief = role_brief(stand, t)

    why = note(stand, f"бриф:\n{fresh_brief}")
    assert brief.spec_gate_note(stand.conn, t.id) == second, why
    assert second.strip() in fresh_brief, why
    assert first.strip() not in fresh_brief, why

    escalate_and_answer(stand, t)

    kept = brief.spec_gate_note(stand.conn, t.id)
    review_ready(stand, t)
    kept_package = package(stand, t)["text"]

    why = note(stand, f"пакет:\n{kept_package}\nжурнал:\n{journal(stand, t)}")
    assert kept == second, why
    assert_wrapped_after(kept_package, REVIEW_PREAMBLE, second, why)
    assert first.strip() not in kept_package, why


# ---------------------------------------------------------------- AC-12


def test_ac12_only_operator_record_of_note_action_counts(stand):
    """Запись действия указания не от `operator` и запись иного действия от `operator` с тем же видом текста указанием не считаются — ни функцией, ни брифом, ни пакетом.

    Сценарий: `approve` без флага, затем в журнал после `state -> spec_gate`
    — запись действия указания случайным исполнителем не-`operator` и запись
    `operator` иного действия: функция — `None`, ни бриф, ни пакет не
    несут ни преамбулы, ни этих текстов. Затем новый проход гейта с
    `approve --note`, после него — запись того же действия чужим
    исполнителем: функция отдаёт текст `operator`, а не более поздний чужой.

    Ловит мутацию: выборка по действию без исполнителя — чужая запись
    даёт указание (или перекрывает указание Оператора); выборка по
    исполнителю `operator` без действия — запись «указание Оператора»
    принята за указание гейта.
    """
    t = new_task(stand)
    _ok, out = approve_plain(stand, t)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    stranger = stand.rng.choice(("fsm", "analyst", "test_author", "reviewer",
                                 "developer"))
    foreign_text, other_text = note_text(stand), note_text(stand)
    store.journal(stand.conn, t.id, stranger, NOTE_ACTION, foreign_text)
    store.journal(stand.conn, t.id, "operator",
                  stand.rng.choice(("указание Оператора", APPROVE_REFUSED,
                                    f"заметка {word(stand)}")), other_text)

    got = brief.spec_gate_note(stand.conn, t.id)
    text_of_brief = role_brief(stand, t)
    review_ready(stand, t)
    pkg = package(stand, t)["text"]

    why = note(stand, f"{stranger}: бриф:\n{text_of_brief}\nпакет:\n{pkg}")
    assert got is None, why
    for part in (text_of_brief, pkg):
        assert BRIEF_PREAMBLE not in part and REVIEW_PREAMBLE not in part, why
        assert foreign_text.strip() not in part, why
        assert other_text.strip() not in part, why

    back_to_gate(stand, t)
    own = note_text(stand)
    _ok, out = approve_note(stand, t, own)
    assert state(stand, t) == "tests_writing", note(stand, f"предпосылка:\n{out}")
    store.journal(stand.conn, t.id, stranger, NOTE_ACTION, note_text(stand))

    assert brief.spec_gate_note(stand.conn, t.id) == own, note(stand, journal(stand, t))


# ---------------------------------------------------------------- AC-14


def test_ac14_help_names_note_in_approve_entry():
    """Справка `artel.py` (строка `approve <id>` и её продолжения с отступом больше двух пробелов) называет `--note`.

    Ловит мутацию: `--note` дописан строкой с отступом в два пробела — по
    справке это новая команда, а не продолжение `approve`; флаг не внесён в
    справку вовсе.
    """
    lines = (artel.__doc__ or "").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if re.match(r"^  approve <id>", line))
    entry = [lines[start]]
    for line in lines[start + 1:]:
        if not line.strip() or len(line) - len(line.lstrip()) <= 2:
            break
        entry.append(line)
    assert any(NOTE_FLAG in line for line in entry), "\n".join(entry)


# ---------------------------------------------------------------- AC-15


def escalated_with_answer(stand, t) -> None:
    """Задача — в `escalated` с ответом `ANSWER-1.md` в ссылке документов: `approve` без флага снимает эскалацию."""
    store.update_task(stand.conn, t.id, state="escalated", escalated_from=None,
                      answer_baseline=0)
    put_doc(stand, t, "ANSWER-1.md", f"Ответ {word(stand, 10)}\n")


def run_with_change_under_lease(stand, t, change, argv_tail: list) -> str:
    """`approve` с подменой `lease.run_locked`: до вызова обработчика под lease — `change()`; вывод команды."""
    real = lease.run_locked
    done = []

    def locked(*args, **kwargs):
        if not done:
            done.append(True)
            change()
        return real(*args, **kwargs)

    with mock.patch.object(lease, "run_locked", locked):
        _ok, out = cli("approve", t.id, *argv_tail)
    assert done, note(stand, f"предпосылка: lease не брался:\n{out}")
    return out


@pytest.mark.parametrize("kind", ["skip", "division"])
def test_ac15_spec_changed_before_lease_refused_under_lease(stand, kind):
    """SPEC получил `skip_tests`/деление между проверкой до lease и обработчиком — `approve --note` отказывает под lease без записи отказа и указания, задача на гейте.

    Сценарий: подмена `lease.run_locked` кладёт в ссылку документов новый
    SPEC вида `kind` перед вызовом настоящего `run_locked`.

    Ловит мутацию: повтор проверки пути под lease удалён — задача уходит в
    `in_dev` (skip_tests) или делится на части; повтор пишет мягкий отказ
    «approve отклонён» в журнал вместо отказа без записей.
    """
    t = new_task(stand)
    count = len(rows(stand, t))
    path = write_file(stand, note_text(stand))

    out = run_with_change_under_lease(
        stand, t, lambda: put_doc(stand, t, "SPEC.md", spec_text(stand, t.id, kind)),
        [NOTE_FLAG, path])

    why = note(stand, f"{kind}: вывод:\n{out}\nжурнал:\n{journal(stand, t)}")
    assert REFUSED_SIGN in out, why
    assert state(stand, t) == "spec_gate", why
    assert note_rows(stand, t) == [], why
    added = rows(stand, t)[count:]
    assert [r for r in added if r["action"] == APPROVE_REFUSED] == [], why
    assert [r for r in store.all_tasks(stand.conn)
            if r["parent_task_id"] == t.id] == [], why


def test_ac15_state_changed_to_escalated_before_lease_refused(stand):
    """Задача ушла в `escalated` с `ANSWER-1.md` между проверкой до lease и обработчиком — `approve --note` отказывает «допустим только в состоянии spec_gate», задача в `escalated`, записи указания нет; тот же сценарий без `--note` снимает эскалацию.

    Сценарий: подмена `lease.run_locked` переводит задачу в `escalated` и
    кладёт `ANSWER-1.md` перед вызовом настоящего `run_locked`. Контроль —
    вторая задача, та же подмена, `approve` без флага: задача выходит из
    `escalated` (обычный путь `_approve_escalated`), поэтому отказ первой
    задачи — именно повтор проверки состояния под lease.

    Ловит мутацию: повтор проверки состояния под lease удалён — `approve
    --note` проходит обычный переход из `escalated` (задача в `in_dev`).
    """
    t = new_task(stand)
    control = new_task(stand)
    path = write_file(stand, note_text(stand))

    out = run_with_change_under_lease(
        stand, t, lambda: escalated_with_answer(stand, t), [NOTE_FLAG, path])
    control_out = run_with_change_under_lease(
        stand, control, lambda: escalated_with_answer(stand, control), [])

    why = note(stand, f"вывод:\n{out}\nконтроль:\n{control_out}\n"
                      f"журнал:\n{journal(stand, t)}")
    assert state(stand, control) != "escalated", why
    assert ONLY_SPEC_GATE in out, why
    assert state(stand, t) == "escalated", why
    assert note_rows(stand, t) == [], why
