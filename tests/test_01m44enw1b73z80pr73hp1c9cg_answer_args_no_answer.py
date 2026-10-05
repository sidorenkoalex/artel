"""Разбор аргументов `answer` (отказ на ключ, отсутствующий файл, лишние
аргументы) и снятие эскалации «нужен шаг роли» без ANSWER только флагом
`approve --no-answer` (AC-1..AC-8).

Группа: долгоживущий

Красен до реализации: `answer <id> --from <файл>` берёт «--from» за путь файла (в `escalated` — под lease, в `in_dev` — чтением файла) и отказывает текстом «файл ответа не прочитан» без синтаксиса команды, `answer <id>` падает `IndexError`, лишние аргументы молча отбрасываются (AC-1); `approve` снимает эскалацию конфликта подтяжки без ANSWER, флага `--no-answer` диспетчер не знает и берёт его за sha (AC-2, AC-3 — старый ANSWER, AC-4, AC-7); подсказки `auto` в `escalated` предлагают голый `artel.py approve <id>`, справка и `docs/operator-session.md` о флаге молчат (AC-8).

AC-6 (эскалация без метки снимается прежним `approve`), половина AC-3
(ANSWER после эскалации — прежний переход) и AC-5 (сверка
`answer_baseline` держит и при флаге) зелены с рождения: они держат
сегодняшнее поведение против проверки, которая станет требовать ответ
или флаг шире, чем у эскалации с меткой «нужен шаг роли», либо пропустит
сверку `answer_baseline` по флагу.

Песочница — `tests.sandbox.LightTransitionSandbox` (диск — источник
артефактов, git подменён). Команды идут через диспетчер `artel.main` с
подменённым `sys.argv` — тем же входом, что у Оператора; признак роли
(`ARTEL_ROLE`) из окружения снят. Эскалации собираются записями журнала
так, как их пишут точки эскалации: `state -> escalated`, за ней — метка
«нужен шаг роли» (`pull.PULL_CONFLICT_ROLE_STEP_MARKER` либо
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`). ANSWER — запись журнала
«ANSWER создан…» (вид команды `answer` либо `zones-extend`) и файл
`ANSWER-n.md` на диске. Тексты эскалаций, имена файлов, ключи, число
лишних аргументов и порядок случаев берутся случайно при каждом запуске;
зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, auto, config, fsm, lease, pull, runner, store
from tests.sandbox import LightTransitionSandbox

REPO = Path(__file__).resolve().parent.parent
OPERATOR_SESSION = REPO / "docs" / "operator-session.md"

NO_ANSWER_FLAG = "--no-answer"
RETURN_DETAIL = "эскалация разрешена, продолжаем"
BASELINE_REFUSAL_ACTION = "approve отклонён: нет ANSWER"
ANSWER_SYNTAX = re.compile(r"artel\.py answer \S+ <файл-с-ответом>")
ANSWER_COMMAND = re.compile(r"artel\.py answer \S+ <файл")
ROLE_STEP_MARKERS = (pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                     fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER)
# Записи бухгалтерии вокруг команды, не события самой команды.
FIXATION_ACTION = "sha зафиксирован"

WORDS = ("разбор", "падение", "причина", "модуль", "фикстура", "импорт",
         "порядок", "ветка", "журнал", "шаг", "проверка", "карта")
FLAG_KEYS = ("--from", "--file", "--path", "--answer", "--text")
NOT_ESCALATED_STATES = ("in_dev", "review", "tests_writing", "spec_writing",
                        "verifying", "done")
NO_MARKER_DETAILS = (
    "агент упал после всех попыток: rc=1",
    "лимит итераций ревью исчерпан",
    "лимит отказов приёмки исчерпан",
    "подтяжка отказала после очистки рабочей копии",
    "потолок ожидания CI в verifying",
    "инцидент целостности на старте шага",
)


class HaltCycle(BaseException):
    """Прерывает цикл `auto` на первом шаге роли сценария."""


class NoAnswerSandbox(LightTransitionSandbox):
    """Задача лёгкой песочницы; команды — через `artel.main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.tdir.mkdir(parents=True, exist_ok=True)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

    # ------------------------------------------------------------ команда

    def main(self, *args: str) -> tuple:
        """(вывод вместе с текстом отказа, код выхода либо None, имя
        необработанного исключения либо None)."""
        buf = io.StringIO()
        code = error = None
        with mock.patch.object(sys, "argv", ["artel.py", *args]), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
            except Exception as exc:  # noqa: BLE001 — ловим именно его
                error = f"{type(exc).__name__}: {exc}"
        return buf.getvalue(), code, error

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    # ------------------------------------------------------------ журнал

    def rows(self) -> list:
        return list(store.task_steps(store.db(), self.TASK))

    def meaningful_rows(self) -> list:
        return [r for r in self.rows()
                if r["actor"] != "lease" and r["action"] != FIXATION_ACTION]

    def dump(self) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows())

    def journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(store.db(), self.TASK, actor, action, detail)

    # ------------------------------------------------------------ сценарий

    def words(self) -> str:
        return " ".join(self.rng.choice(WORDS)
                        for _ in range(self.rng.randrange(3, 8)))

    def token(self) -> str:
        return f"m{self.rng.randrange(10 ** 9)}"

    def pull_conflict_detail(self) -> str:
        files = ", ".join(f"kod/f_{self.rng.randrange(10 ** 6)}.py"
                          for _ in range(self.rng.randrange(1, 4)))
        return f"конфликт подтяжки main: {files} — {self.token()}"

    def enter_in_dev(self) -> None:
        """Первый вход в `in_dev` и отработавший шаг developer."""
        self.journal("fsm", "state -> in_dev", f"вход в разработку {self.token()}")
        self.journal("developer", "agent run finished", "rc=0, шаг до эскалации")

    def escalate(self, detail: str, marker: str | None,
                 escalated_from: str | None) -> None:
        """Эскалация так, как её пишет точка эскалации: переход, затем
        метка «нужен шаг роли» с тем же detail (если она есть)."""
        store.update_task(store.db(), self.TASK, state="escalated",
                          escalated_from=escalated_from)
        self.journal("fsm", "state -> escalated", detail)
        if marker is not None:
            self.journal("fsm", marker, detail)

    def answer_count(self) -> int:
        return len(list(self.tdir.glob("ANSWER-*.md")))

    def give_answer(self, via: str) -> None:
        """ANSWER так, как его оставляют `answer` или `zones-extend`:
        следующий `ANSWER-n.md` и запись «ANSWER создан…»."""
        n = self.answer_count() + 1
        name = f"ANSWER-{n}.md"
        (self.tdir / name).write_text(
            f"---\ntask: {self.TASK}\ntype: answer\nschema_version: 1\n---\n\n"
            f"# ANSWER-{n}\n\n{self.words()}\n", encoding="utf-8")
        if via == "answer":
            action = "ANSWER создан, ждёт approve"
        else:
            action = (f"ANSWER создан (мандат на расширение зон: "
                      f"kod/z_{self.rng.randrange(10 ** 6)}/)")
        self.journal("operator", action, name)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def assert_refused_without_answer(self, out: str, last_id: int,
                                      what: str) -> None:
        """Отказ AC-2: задача в `escalated`, текст называет ANSWER,
        команду answer и флаг, в журнале после `last_id` — запись отказа."""
        self.assertEqual("escalated", self.state(), self.why(
            f"{what}: эскалация снята без ANSWER:\n{out}\n{self.dump()}"))
        self.assertIn("ANSWER", out, self.why(f"{what}: текст не называет ANSWER:\n{out}"))
        self.assertRegex(out, ANSWER_COMMAND, self.why(
            f"{what}: текст не называет команду answer:\n{out}"))
        self.assertIn(NO_ANSWER_FLAG, out, self.why(
            f"{what}: текст не называет флаг:\n{out}"))
        new = [r for r in self.meaningful_rows() if r["id"] > last_id]
        self.assertTrue(any("отклон" in (r["action"] or "") for r in new),
                        self.why(f"{what}: нет записи отказа:\n{self.dump()}"))

    def assert_returned(self, back: str, out: str, rows_before: int) -> None:
        self.assertEqual(back, self.state(),
                         self.why(f"approve не вернул задачу в {back}:\n{out}\n"
                                  f"{self.dump()}"))
        new = self.rows()[rows_before:]
        self.assertTrue(
            any(r["action"] == f"state -> {back}" and r["detail"] == RETURN_DETAIL
                for r in new),
            self.why(f"нет записи «state -> {back}» с «{RETURN_DETAIL}»:\n"
                     f"{self.dump()}"))


def bare_approve(text: str, task: str) -> list:
    """Вхождения `artel.py approve <id>`, в предложении которых нет
    `--no-answer` (предложение — до `;` или конца строки)."""
    found = []
    for m in re.finditer(rf"artel\.py approve {re.escape(task)}", text):
        tail = re.split(r"[;\n]", text[m.end():], maxsplit=1)[0]
        if NO_ANSWER_FLAG not in tail:
            found.append(text[m.start():m.end() + len(tail)])
    return found


def blocks(text: str) -> list:
    """Абзацы и пункты списка markdown/справки."""
    return [b for b in re.split(r"\n\s*\n|\n(?=\s*- )", text) if b.strip()]


# --------------------------------------------------------------------- AC-1

class AnswerArgumentsRefusedTest(NoAnswerSandbox):

    def answer_file(self) -> str:
        path = self.root / f"otvet-{self.rng.randrange(1 << 40)}.txt"
        path.write_text(f"Ответ Оператора {self.token()}: {self.words()}.\n",
                        encoding="utf-8")
        return str(path)

    def cases(self) -> list:
        """(вид, аргументы после `answer`, что обязан назвать отказ)."""
        key = self.rng.choice(FLAG_KEYS)
        missing = str(self.root / f"net-{self.rng.randrange(1 << 40)}.txt")
        extra = [self.answer_file()] + [
            self.rng.choice((self.token(), self.answer_file(), "--yes"))
            for _ in range(self.rng.randrange(1, 4))]
        return [
            ("ключ с файлом", [self.TASK, key, self.answer_file()], key),
            ("ключ без файла", [self.TASK, key], key),
            ("нет файла", [self.TASK], None),
            ("несуществующий файл", [self.TASK, missing], missing),
            ("лишние аргументы", [self.TASK, *extra], None),
        ]

    def test_ac1_answer_refuses_key_missing_file_and_extra_args(self):
        """`answer` с ключом вместо файла, без файла, с несуществующим файлом и с лишними аргументами — отказ в разборе.

        Для `escalated` и `in_dev` (в случайном порядке) и каждого вида
        аргументов: `answer <id> <ключ> <существующий-файл>` и
        `answer <id> <ключ>` (ключ — случайный «--…»), `answer <id>`,
        `answer <id> <несуществующий-путь>`, `answer <id> <файл> <ещё 1–3
        аргумента>`. Каждый вызов кончается ненулевым `SystemExit` без
        необработанного исключения; текст называет синтаксис
        `artel.py answer <id> <файл-с-ответом>` и полученный ключ либо
        несуществующий путь; в журнале задачи нет ни одной новой записи,
        `lease.run_locked` не вызван, строки lease нет, коммита ANSWER
        (`artifact_branch.commit_files`) не было, состояние прежнее.

        Ловит мутацию: «--from» по-прежнему передаётся как путь файла — в
        `escalated` берётся lease (вызов `run_locked`, записи lease в
        журнале), текст «файл ответа не прочитан» без синтаксиса команды;
        проверка числа аргументов отсутствует — `answer <id> <файл> <лишнее>`
        создаёт ANSWER (коммит, запись «ANSWER создан»/«указание
        Оператора»); `answer <id>` падает `IndexError`; проверка ключа
        стоит только в ветке `escalated` — в `in_dev` файл читается и
        принимается как указание.
        """
        states = ["escalated", "in_dev"]
        self.rng.shuffle(states)
        for state in states:
            cases = self.cases()
            self.rng.shuffle(cases)
            for kind, args, named in cases:
                with self.subTest(state=state, kind=kind, зерно=self.seed):
                    self.set_state(state)
                    rows_before = len(self.rows())
                    with mock.patch.object(lease, "run_locked",
                                           wraps=lease.run_locked) as locked:
                        out, code, error = self.main("answer", *args)

                    what = f"{state}/{kind} {args[1:]}"
                    self.assertIsNone(error, self.why(
                        f"{what}: необработанное исключение {error}\n{out}"))
                    self.assertNotIn(code, (None, 0), self.why(
                        f"{what}: команда не отказала:\n{out}"))
                    self.assertRegex(out, ANSWER_SYNTAX, self.why(
                        f"{what}: отказ не называет синтаксис:\n{out}"))
                    if named is not None:
                        self.assertIn(named, out, self.why(
                            f"{what}: отказ не называет «{named}»:\n{out}"))
                    self.assertEqual([], [dict(r) for r in self.rows()[rows_before:]],
                                     self.why(f"{what}: новые записи журнала"))
                    self.assertFalse(locked.called, self.why(f"{what}: lease взят"))
                    self.assertIsNone(store.lease_row(store.db(), self.TASK),
                                      self.why(f"{what}: строка lease есть"))
                    self.assertEqual(state, self.state(), self.why(what))


# --------------------------------------------------------------------- AC-2

class ApproveWithoutAnswerRefusedTest(NoAnswerSandbox):

    def test_ac2_approve_after_pull_conflict_without_answer_is_refused(self):
        """`approve` после эскалации конфликта подтяжки без ANSWER и без флага — отказ, задача в `escalated`.

        Задача прошла шаг developer и эскалирована по конфликту подтяжки:
        `state -> escalated` и за ней `PULL_CONFLICT_ROLE_STEP_MARKER` со
        случайным списком файлов; `escalated_from` — `in_dev` либо пусто
        (случайно). ANSWER нет. `approve <id>` оставляет задачу в
        `escalated`; вывод называет ANSWER, команду `artel.py answer <id>
        <файл…>` и флаг `--no-answer`; в журнале новая запись отказа.

        Ловит мутацию: новая проверка смотрит только `answer_baseline` (как
        сегодня) — эскалация конфликта подтяжки снимается без ответа,
        задача в `in_dev`; проверка ищет только
        `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` — та же утечка для
        метки подтяжки; отказ печатается, но не журналируется — записи
        отказа нет; отказ не называет флаг — Оператор не узнаёт выход.
        """
        self.enter_in_dev()
        self.escalate(self.pull_conflict_detail(), pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                      self.rng.choice(("in_dev", None)))
        last_id = self.rows()[-1]["id"]

        out, _code, error = self.main("approve", self.TASK)

        self.assertIsNone(error, self.why(f"исключение {error}\n{out}"))
        self.assert_refused_without_answer(out, last_id, "approve без флага")


# --------------------------------------------------------------------- AC-3

class AnswerPlacementTest(NoAnswerSandbox):

    def test_ac3_answer_before_last_escalation_does_not_count(self):
        """ANSWER, данный до последней записи `state -> escalated`, не снимает эскалацию с меткой.

        Первая эскалация (с меткой подтяжки или артефакта роли — случайно)
        получила ANSWER (вид `answer` либо `zones-extend`) и была снята;
        затем задача снова эскалирована по конфликту подтяжки без нового
        ANSWER. `approve <id>` без флага отклоняется так же, как в AC-2:
        задача в `escalated`, вывод называет ANSWER, команду answer и флаг,
        в журнале запись отказа.

        Ловит мутацию: «ANSWER есть» проверяется по наличию любого
        `ANSWER-*.md` или любой записи «ANSWER создан» в журнале задачи, а
        не после последней `state -> escalated` — старый ответ снимает
        новую эскалацию, задача уходит в `in_dev`.
        """
        self.enter_in_dev()
        self.escalate(self.pull_conflict_detail(), self.rng.choice(ROLE_STEP_MARKERS),
                      "in_dev")
        self.give_answer(self.rng.choice(("answer", "zones-extend")))
        store.update_task(store.db(), self.TASK, state="in_dev", escalated_from=None)
        self.journal("operator", "state -> in_dev", RETURN_DETAIL)
        self.journal("developer", "agent run finished", "rc=0, шаг после ответа")
        self.escalate(self.pull_conflict_detail(), pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                      self.rng.choice(("in_dev", None)))
        last_id = self.rows()[-1]["id"]

        out, _code, error = self.main("approve", self.TASK)

        self.assertIsNone(error, self.why(f"исключение {error}\n{out}"))
        self.assert_refused_without_answer(out, last_id, "старый ANSWER")

    def test_ac3_answer_after_escalation_returns_without_flag(self):
        """ANSWER после эскалации с меткой (командой `answer` или `zones-extend`) — `approve` без флага снимает её прежним переходом.

        Для обоих видов ANSWER (в случайном порядке, каждый — на своей
        эскалации той же задачи): эскалация с меткой «нужен шаг роли»
        (подтяжки или артефакта роли — случайно), `escalated_from` —
        случайное состояние либо пусто; затем ANSWER. `approve <id>` без
        флага переводит задачу в `escalated_from` (либо `in_dev`) с записью
        `state -> <возврат>` и detail «эскалация разрешена, продолжаем».

        Ловит мутацию: в ANSWER засчитывается только действие «ANSWER
        создан, ждёт approve» команды `answer` — ответ мандатом
        `zones-extend` («ANSWER создан (мандат …)») не снимает эскалацию;
        новая проверка требует флаг всегда при метке, даже с ответом —
        задача остаётся в `escalated`; возврат сделан с новым текстом
        записи перехода — нет «эскалация разрешена, продолжаем».
        """
        vias = ["answer", "zones-extend"]
        self.rng.shuffle(vias)
        self.enter_in_dev()
        for via in vias:
            with self.subTest(via=via, зерно=self.seed):
                back_from = self.rng.choice(("in_dev", "tests_writing", None))
                self.escalate(self.pull_conflict_detail(),
                              self.rng.choice(ROLE_STEP_MARKERS), back_from)
                self.give_answer(via)
                rows_before = len(self.rows())

                out, _code, error = self.main("approve", self.TASK)

                self.assertIsNone(error, self.why(f"{via}: исключение {error}\n{out}"))
                self.assert_returned(back_from or "in_dev", out, rows_before)
                self.journal("developer", "agent run finished", "rc=0")


# --------------------------------------------------------------------- AC-4

class NoAnswerFlagReturnsTest(NoAnswerSandbox):

    def run_auto_until_first_step(self) -> list:
        """`auto` до первого шага роли; порядок событий «advance»/«step»."""
        events: list = []
        real_advance = fsm.cmd_advance

        def advance(*args, **kwargs):
            events.append("advance")
            return real_advance(*args, **kwargs)

        def step(task_id, session_id=None):
            conn = store.db()
            events.append(f"step:{runner.step_role(store.get_task(conn, task_id))}")
            store.journal(conn, task_id, "developer", "agent run finished",
                          "rc=0, сценарий песочницы")
            raise HaltCycle()

        buf = io.StringIO()
        with mock.patch.object(fsm, "cmd_advance", side_effect=advance), \
                mock.patch.object(runner, "cmd_run", side_effect=step), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                auto.cmd_auto(self.TASK)
            except HaltCycle:
                pass
        self.auto_out = buf.getvalue()
        return events

    def test_ac4_no_answer_flag_returns_with_journaled_detail_and_developer_step(self):
        """`approve <id> --no-answer` после конфликта подтяжки без ANSWER — прежний возврат, запись Оператора с текстом эскалации, затем шаг developer.

        Задача прошла шаг developer и эскалирована по конфликту подтяжки
        (случайный detail, `escalated_from` — `in_dev` либо пусто), ANSWER
        нет. `approve <id> --no-answer`: задача в `in_dev`, запись
        `state -> in_dev` с «эскалация разрешена, продолжаем»; среди новых
        записей — отдельная (не запись перехода) запись актора `operator`,
        несущая detail последней `state -> escalated`. Затем цикл `auto`:
        первое событие — шаг роли developer, `fsm.cmd_advance`
        (предварительный advance) до него не вызывается.

        Ловит мутацию: флаг не распознан (принят за sha или отброшен) —
        отказ AC-2, задача в `escalated`; запись о снятии без ответа не
        пишется или пишется без текста эскалации — нет записи Оператора с
        detail; флаг пишет свою запись как `state -> in_dev` с иным detail
        либо пишет лишний переход состояния между меткой и возвратом —
        метка гасится, пред-advance идёт раньше шага developer (первое
        событие «advance»).
        """
        self.enter_in_dev()
        detail = self.pull_conflict_detail()
        self.escalate(detail, pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                      self.rng.choice(("in_dev", None)))
        rows_before = len(self.rows())

        out, _code, error = self.main("approve", self.TASK, NO_ANSWER_FLAG)

        self.assertIsNone(error, self.why(f"исключение {error}\n{out}"))
        self.assert_returned("in_dev", out, rows_before)
        new = self.rows()[rows_before:]
        noted = [r for r in new
                 if r["actor"] == "operator"
                 and not (r["action"] or "").startswith("state -> ")
                 and detail in f"{r['action']} {r['detail'] or ''}"]
        self.assertTrue(noted, self.why(
            f"нет записи Оператора с текстом эскалации «{detail}»:\n{self.dump()}"))

        events = self.run_auto_until_first_step()

        self.assertTrue(events, self.why(f"auto ничего не сделал:\n{self.auto_out}"))
        self.assertEqual("step:developer", events[0], self.why(
            f"до шага developer: {events}\n{self.auto_out}\n{self.dump()}"))


# --------------------------------------------------------------------- AC-5

class NoAnswerFlagKeepsBaselineTest(NoAnswerSandbox):

    def test_ac5_flag_does_not_bypass_answer_baseline(self):
        """Эскалация со структурированным вопросом (`answer_baseline` задан) без нового ANSWER — прежний отказ и с флагом.

        `escalated_from` — `spec_writing`/`tests_writing`/`review`
        (случайно), на диске k прежних `ANSWER-*.md` (k случайно 0–2),
        `answer_baseline = k`; метка артефакта роли за переходом есть
        либо нет (случайно). И `approve <id>`, и `approve <id>
        --no-answer` (в случайном порядке) оставляют задачу в `escalated`
        и пишут запись «approve отклонён: нет ANSWER».

        Ловит мутацию: флаг пропускает и сверку `answer_baseline` (ветка
        флага возвращает задачу до неё) — задача уходит в
        `escalated_from` без ответа на вопрос роли; новая проверка стоит
        раньше сверки и при флаге отвечает своим текстом — записи
        «approve отклонён: нет ANSWER» нет.
        """
        k = self.rng.randrange(0, 3)
        for _ in range(k):
            self.give_answer("answer")
        back_from = self.rng.choice(("spec_writing", "tests_writing", "review"))
        marker = self.rng.choice((fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER, None))
        self.escalate(f"вопрос роли {self.token()}: {self.words()}", marker, back_from)
        store.update_task(store.db(), self.TASK, answer_baseline=k)
        variants = [(), (NO_ANSWER_FLAG,)]
        self.rng.shuffle(variants)
        for flags in variants:
            with self.subTest(flags=flags, k=k, marker=bool(marker), зерно=self.seed):
                rows_before = len(self.rows())

                out, _code, error = self.main("approve", self.TASK, *flags)

                self.assertIsNone(error, self.why(f"исключение {error}\n{out}"))
                self.assertEqual("escalated", self.state(), self.why(
                    f"{flags}: эскалация снята без ANSWER:\n{out}"))
                self.assertIn(BASELINE_REFUSAL_ACTION,
                              [r["action"] for r in self.rows()[rows_before:]],
                              self.why(f"{flags}: нет прежнего отказа:\n{self.dump()}"))


# --------------------------------------------------------------------- AC-6

class EscalationWithoutMarkerTest(NoAnswerSandbox):

    def test_ac6_escalation_without_marker_returns_without_answer_or_flag(self):
        """Эскалация без метки «нужен шаг роли» снимается `approve <id>` без ANSWER и флага прежним переходом.

        Detail эскалации — случайный из перечня эскалаций без метки (провал
        агента, лимиты, подтяжка после очистки, CI, инцидент);
        `escalated_from` — случайное состояние либо пусто. Случайно у
        задачи есть и прошлая, уже снятая эскалация с меткой и ответом —
        до последней `state -> escalated`. `approve <id>` переводит задачу
        в `escalated_from` (либо `in_dev`) с записью
        «эскалация разрешена, продолжаем».

        Ловит мутацию: метка ищется во всём журнале задачи, а не после
        последней `state -> escalated` — прошлая метка требует ответа или
        флага, задача остаётся в `escalated`; ответ требуется от любой
        эскалации — тот же отказ.
        """
        self.enter_in_dev()
        earlier = bool(self.rng.randrange(2))
        if earlier:
            self.escalate(self.pull_conflict_detail(),
                          self.rng.choice(ROLE_STEP_MARKERS), "in_dev")
            self.give_answer(self.rng.choice(("answer", "zones-extend")))
            store.update_task(store.db(), self.TASK, state="in_dev",
                              escalated_from=None)
            self.journal("operator", "state -> in_dev", RETURN_DETAIL)
            self.journal("developer", "agent run finished", "rc=0")
        back_from = self.rng.choice(("in_dev", "review", "tests_writing", None))
        self.escalate(f"{self.rng.choice(NO_MARKER_DETAILS)} {self.token()}",
                      None, back_from)
        rows_before = len(self.rows())

        out, _code, error = self.main("approve", self.TASK)

        self.assertIsNone(error, self.why(f"исключение {error}\n{out}"))
        print(f"прошлая эскалация с меткой: {earlier}")
        self.assert_returned(back_from or "in_dev", out, rows_before)


# --------------------------------------------------------------------- AC-7

class NoAnswerFlagOutsideEscalatedTest(NoAnswerSandbox):

    def test_ac7_no_answer_flag_outside_escalated_is_refused_by_name(self):
        """`approve <id> --no-answer` вне `escalated` — именованный отказ, состояние прежнее.

        Три случайных состояния из не-`escalated` (разработка, ревью,
        тесты, SPEC, CI, закрытая задача), в каждом `approve <id>
        --no-answer`: состояние не меняется, вывод называет `--no-answer`
        и `escalated`.

        Ловит мутацию: флаг разбирается, но допустимость состояния не
        проверяется — прежний вывод «в состоянии … нечего подтверждать»
        без имени флага; флаг принят за sha — отказ о sha без слов
        `--no-answer`/`escalated`.
        """
        for state in self.rng.sample(NOT_ESCALATED_STATES, 3):
            with self.subTest(state=state, зерно=self.seed):
                self.set_state(state)

                out, _code, error = self.main("approve", self.TASK, NO_ANSWER_FLAG)

                self.assertIsNone(error, self.why(f"{state}: исключение {error}\n{out}"))
                self.assertEqual(state, self.state(), self.why(
                    f"{state}: состояние сменилось:\n{out}"))
                self.assertIn(NO_ANSWER_FLAG, out, self.why(
                    f"{state}: отказ не называет флаг:\n{out}"))
                self.assertIn("escalated", out, self.why(
                    f"{state}: отказ не называет escalated:\n{out}"))


# --------------------------------------------------------------------- AC-8

class AdviceAfterMarkedEscalationTest(NoAnswerSandbox):

    def test_ac8_auto_stop_advice_offers_flag_or_answer_only_for_marked(self):
        """Подсказка `auto_stop_advice` в `escalated`: с меткой без ANSWER — флаг или команда answer, без метки — прежний `approve`.

        Случай с меткой (подтяжки или артефакта роли — случайно) без
        ANSWER после эскалации: подсказка содержит `--no-answer` либо
        `artel.py answer <id> <файл…>` и ни одного `artel.py approve <id>`
        без флага. Случай без метки (провал агента): подсказка содержит
        `artel.py approve <id>` и не содержит `--no-answer`.

        Ловит мутацию: подсказка `config.AUTO_STOP["escalated"]` не
        различает случаи — с меткой предлагается голый `approve <id>`;
        флаг дописан в общую подсказку — эскалация без метки получает
        `--no-answer`.
        """
        self.enter_in_dev()
        self.escalate(self.pull_conflict_detail(), self.rng.choice(ROLE_STEP_MARKERS),
                      self.rng.choice(("in_dev", None)))

        _reason, hint = auto.auto_stop_advice(store.db(), self.TASK, "escalated")

        self.assertTrue(NO_ANSWER_FLAG in hint or ANSWER_COMMAND.search(hint),
                        self.why(f"с меткой: нет флага и команды answer: {hint}"))
        self.assertEqual([], bare_approve(hint, self.TASK),
                         self.why(f"с меткой: голый approve: {hint}"))

        store.update_task(store.db(), self.TASK, state="in_dev", escalated_from=None)
        self.journal("operator", "state -> in_dev", RETURN_DETAIL)
        self.escalate(f"{NO_MARKER_DETAILS[0]} {self.token()}", None, None)

        _reason, plain = auto.auto_stop_advice(store.db(), self.TASK, "escalated")

        self.assertIn(f"artel.py approve {self.TASK}", plain,
                      self.why(f"без метки: подсказка не прежняя: {plain}"))
        self.assertNotIn(NO_ANSWER_FLAG, plain,
                         self.why(f"без метки: флаг в подсказке: {plain}"))

    def test_ac8_pull_conflict_streak_stop_hint_has_no_bare_approve(self):
        """Остановка `auto` по второй подряд эскалации конфликта подтяжки — подсказка с флагом или командой answer, без голого approve.

        Журнал: шаг developer, эскалация конфликта подтяжки с меткой,
        ANSWER, возврат, ещё шаг developer. Предварительный advance цикла
        (`fsm.cmd_advance` подменён) снова эскалирует задачу по конфликту
        подтяжки с меткой — вторая подряд. Строка «дальше:» остановки
        содержит `--no-answer` либо `artel.py answer <id> <файл…>` и ни
        одного `artel.py approve <id>` без флага.

        Ловит мутацию: подсказка стоп-крана серии осталась прежней
        («artel.py answer/approve <id>») — в ней нет ни флага, ни команды
        answer с файлом; в ней голый `artel.py approve <id>`.
        """
        self.enter_in_dev()
        self.escalate(self.pull_conflict_detail(), pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                      None)
        self.give_answer("answer")
        store.update_task(store.db(), self.TASK, state="in_dev", escalated_from=None)
        self.journal("operator", "state -> in_dev", RETURN_DETAIL)
        self.journal("developer", "agent run finished", "rc=0, шаг после ответа")
        second = self.pull_conflict_detail()

        def advance(task_id, session_id=None):
            conn = store.db()
            store.set_state(conn, task_id, "escalated", "fsm",
                            expected_state="in_dev", detail=second)
            store.journal(conn, task_id, "fsm", pull.PULL_CONFLICT_ROLE_STEP_MARKER,
                          second)
            return None

        def step(task_id, session_id=None):
            raise HaltCycle()

        buf = io.StringIO()
        with mock.patch.object(fsm, "cmd_advance", side_effect=advance), \
                mock.patch.object(runner, "cmd_run", side_effect=step), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                auto.cmd_auto(self.TASK)
            except HaltCycle:
                pass
        out = buf.getvalue()

        hints = [line.split("дальше:", 1)[1] for line in out.splitlines()
                 if "дальше:" in line]
        self.assertTrue(hints, self.why(f"остановки с подсказкой нет:\n{out}"))
        hint = hints[-1]
        self.assertIn("конфликт подтяжки", out, self.why(
            f"остановка не по серии конфликтов:\n{out}"))
        self.assertTrue(NO_ANSWER_FLAG in hint or ANSWER_COMMAND.search(hint),
                        self.why(f"нет флага и команды answer: {hint}"))
        self.assertEqual([], bare_approve(hint, self.TASK),
                         self.why(f"голый approve: {hint}"))


class HelpAndOperatorSessionTest(unittest.TestCase):

    def test_ac8_help_describes_answer_refusal_instruction_and_flag(self):
        """Справка `artel.py`: абзацы о `answer` называют указание в `in_dev`/`review` и отказ на ключ; `approve` — флаг `--no-answer`.

        Абзацы справки (`artel.__doc__`), где описана команда `` `answer ``,
        вместе содержат «указани», «in_dev», «review» и «ключ»; хотя бы
        один абзац, называющий `approve`, содержит `--no-answer`.

        Ловит мутацию: справка не обновлена — абзац `answer` по-прежнему
        говорит, что файл без строки мандата в `in_dev`/`review`
        отказывает, о ключе молчит; флаг реализован, но в строку команд
        `approve` не добавлен.
        """
        doc = artel.__doc__ or ""
        answer_text = "\n".join(b for b in blocks(doc) if re.search(r"`answer\b", b))
        for piece in ("указани", "in_dev", "review", "ключ"):
            self.assertIn(piece, answer_text,
                          f"справка answer не называет «{piece}»:\n{answer_text}")
        self.assertTrue(any("approve" in b and NO_ANSWER_FLAG in b for b in blocks(doc)),
                        "справка approve не называет --no-answer")

    def test_ac8_operator_session_mentions_flag_and_journal(self):
        """`docs/operator-session.md` несёт абзац о `--no-answer` и о видимости снятия без ответа в журнале.

        Хотя бы один абзац или пункт списка файла содержит и
        `--no-answer`, и «журнал».

        Ловит мутацию: строка о флаге не добавлена или не говорит, что
        снятие без ответа видно в журнале задачи.
        """
        text = OPERATOR_SESSION.read_text(encoding="utf-8")
        self.assertTrue(
            any(NO_ANSWER_FLAG in b and "журнал" in b for b in blocks(text)),
            "в docs/operator-session.md нет абзаца о --no-answer и журнале")


if __name__ == "__main__":
    unittest.main()
