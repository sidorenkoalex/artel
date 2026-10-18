"""Окно тишины `note` открывают только задачи артели и держатель мьютекса
мержа с задачей артели; неизвестный проект держит окно с названной
причиной.

Группа: долгоживущий
Красен до реализации: окно тишины ещё не фильтрует задачи и держателя мьютекса по проекту — внешние задачи держат запись, а неразрешённый проект держит её прежним текстом без «проект задачи не определён» (AC-1, AC-2, AC-3 а/б, AC-4); методы прежнего поведения артели (AC-3 база) и AC-5 зелены и до правки — требование 3 SPEC.

Сценарий целиком через публичную команду `notes.cmd_note` на настоящем
bare `origin`: решение окна наблюдается по тому, ушла ли запись в
`origin/main` сразу (окна нет), либо удержана с текстом «заметка
удержана: <причина>; отправка — …» (окно открыто, причина — между
прологом и «; отправка»). Проект задачи — колонка `target` строки
задачи; внешний проект разрешён записью `config.TARGETS` песочницы
(`declare_target`), неразрешённый — записи там нет.

Идентификаторы задач, сессий и проектов случайны на каждый запуск,
зерно печатается и входит в текст провала.
"""
import os
import random
import shutil
import socket
import tempfile
import unittest
from unittest import mock

from orchestrator import config, notes, store
from tests.sandbox import RealGitSandbox, declare_target, init_bare_origin

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""

HELD_PREFIX = "заметка удержана: "
HELD_SUFFIX = "; отправка"

# Состояния вне окна тишины — для задачи держателя мьютекса (чтобы
# держатель был единственным триггером) и для AC-5. Список фильтруется
# по набору окна динамически: переживает правку набора Оператором.
OUTSIDE_WINDOW = tuple(s for s in ("done", "killed", "escalated")
                       if s not in config.NOTE_SILENCE_WINDOW_STATES)

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class NoteWindowProjectTest(RealGitSandbox):
    """Стенд: bare `origin` с `docs/backlog.md`, пустая БД, без держателя
    мьютекса; внешний проект объявлен в `config.TARGETS` песочницы,
    неразрешённый — нет."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        init_bare_origin(self.origin, self.git)
        self.git("remote", "add", "origin", self.origin)
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "backlog.md").write_text(BACKLOG_TEXT, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "backlog")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.external = "ext" + self.token(6).lower()
        self.ghost = "ghost" + self.token(6).lower()
        declare_target(self.external)
        self.calls = 0

    # --- фикстуры сценария ---

    def token(self, n: int = 10) -> str:
        return "".join(self.rng.choice(_ALPHABET) for _ in range(n))

    def task_id(self, prefix: str = "") -> str:
        return prefix + self.token(16)

    def insert_task(self, task_id: str, state: str, target) -> None:
        """`target` — имя проекта, `""` либо `None` (пустая колонка)."""
        conn = store.db()
        store.insert_task(conn, task_id, "окно тишины", state,
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          10.0)
        if target != config.DEFAULT_TARGET:
            store.update_task(conn, task_id, target=target)

    def set_state(self, task_id: str, state: str) -> None:
        store.update_task(store.db(), task_id, state=state)

    def live_lock(self, task_id: str) -> str:
        session = "s-" + self.token(8).lower()
        store.set_merge_lock(store.db(), task_id, session, os.getpid(),
                             socket.gethostname(), store.now())
        return session

    def origin_backlog(self) -> str:
        return self.git("--git-dir", self.origin, "show",
                        f"{config.MAIN_BRANCH}:docs/backlog.md")

    def note(self) -> tuple[str, str]:
        """Одна обычная запись копилки; (уникальный текст, вывод команды)."""
        self.calls += 1
        marker = f"запись{self.calls}-{self.token(8)}"
        text = f"2 | 18.10 | {marker} | orchestrator/n.py"
        out = self.capture(notes.cmd_note, ["копилка", "--text", text])
        return marker, out

    def assert_pushed(self, marker: str, out: str, ctx: str) -> None:
        msg = f"{ctx}; зерно {self.seed}; вывод: {out!r}"
        self.assertNotIn(HELD_PREFIX, out, msg)
        self.assertIn(marker, self.origin_backlog(), msg)
        self.assertEqual(notes.pending_notes(), [], msg)

    def held_reason(self, marker: str, out: str, ctx: str) -> str:
        msg = f"{ctx}; зерно {self.seed}; вывод: {out!r}"
        self.assertIn(HELD_PREFIX, out, msg)
        self.assertNotIn(marker, self.origin_backlog(), msg)
        return out.split(HELD_PREFIX, 1)[1].split(HELD_SUFFIX, 1)[0]

    # --- AC-1 ---

    def test_ac1_external_task_in_every_window_state_does_not_hold(self):
        """Задача разрешённого внешнего проекта проходит по очереди все
        состояния `config.NOTE_SILENCE_WINDOW_STATES`; в каждом обычный
        `note` уходит в `origin/main` сразу, удержанных записей нет.

        Ловит мутацию: перебор задач окна не фильтрует по проекту (как до
        правки) — первая же запись удержана текстом «задача <id> в
        состоянии …», `origin` её не видит."""
        tid = self.task_id()
        self.insert_task(tid, config.NOTE_SILENCE_WINDOW_STATES[0],
                         self.external)
        for state in config.NOTE_SILENCE_WINDOW_STATES:
            with self.subTest(state=state):
                self.set_state(tid, state)
                marker, out = self.note()
                self.assert_pushed(marker, out,
                                   f"внешняя задача {tid} в {state}")

    # --- AC-2 ---

    def test_ac2_live_holder_with_external_task_does_not_hold(self):
        """Живой держатель мьютекса мержа, чья задача — задача внешнего
        разрешённого проекта (сама в `merge_gate`); других триггеров нет —
        `note` пушит сразу.

        Ловит мутацию: держатель мьютекса учитывается без проверки
        проекта его задачи (как до правки) — запись удержана текстом
        «держатель merge-окна жив …»."""
        tid = self.task_id()
        state = ("merge_gate" if "merge_gate" in config.NOTE_SILENCE_WINDOW_STATES
                 else self.rng.choice(OUTSIDE_WINDOW))
        self.insert_task(tid, state, self.external)
        self.live_lock(tid)
        marker, out = self.note()
        self.assert_pushed(marker, out, f"держатель с внешней задачей {tid}")

    # --- AC-3: прежнее поведение артели ---

    def test_ac3_artel_task_in_every_window_state_holds_with_old_text(self):
        """Задача артели — с `target` артели, с пустой строкой и с NULL —
        в каждом состоянии окна удерживает запись; причина удержания
        буквально «задача <id> в состоянии <state>».

        Ловит мутацию: принадлежность артели проверяется сравнением
        `target == DEFAULT_TARGET` вместо `repo_context.is_artel` — пустой
        или NULL `target` уходит в `resolve`, получает `None`, и причина
        становится «проект задачи не определён» вместо прежнего текста
        (либо, при фильтре «только известные проекты», запись уходит в
        `origin`)."""
        for target in (config.DEFAULT_TARGET, "", None):
            tid = self.task_id()
            self.insert_task(tid, config.NOTE_SILENCE_WINDOW_STATES[0], target)
            for state in config.NOTE_SILENCE_WINDOW_STATES:
                with self.subTest(target=target, state=state):
                    self.set_state(tid, state)
                    marker, out = self.note()
                    ctx = f"задача артели {tid} target={target!r} в {state}"
                    self.assertEqual(self.held_reason(marker, out, ctx),
                                     f"задача {tid} в состоянии {state}",
                                     f"{ctx}; зерно {self.seed}")
            self.set_state(tid, self.rng.choice(OUTSIDE_WINDOW))

    def test_ac3_live_holder_with_artel_task_holds_with_old_text(self):
        """Живой держатель мьютекса с задачей артели (`target` артели,
        пустой, NULL; сама задача вне состояний окна) удерживает запись;
        причина буквально «держатель merge-окна жив (сессия <s>, задача
        <id>)».

        Ловит мутацию: проект задачи держателя берётся сравнением колонки
        `target` с `DEFAULT_TARGET` (пустая/NULL — не артель) либо
        держатель вовсе не проверяется — причина иная или запись ушла в
        `origin`."""
        for target in (config.DEFAULT_TARGET, "", None):
            with self.subTest(target=target):
                tid = self.task_id()
                self.insert_task(tid, self.rng.choice(OUTSIDE_WINDOW), target)
                session = self.live_lock(tid)
                marker, out = self.note()
                ctx = f"держатель {session} с задачей артели {tid} target={target!r}"
                self.assertEqual(
                    self.held_reason(marker, out, ctx),
                    f"держатель merge-окна жив (сессия {session}, задача {tid})",
                    f"{ctx}; зерно {self.seed}")
                store.release_merge_lock(store.db(), session, os.getpid())

    def test_ac3a_external_holder_does_not_mask_artel_task(self):
        """Живой держатель с внешней задачей и одновременно задача артели в
        `in_dev`: запись удержана, причина — «задача <id артели> в
        состоянии in_dev».

        Ловит мутацию: держатель с внешней задачей даёт досрочный
        `return None` вместо перехода к перебору задач — запись уходит в
        `origin` (а до правки причина — текст держателя, не задачи)."""
        ext = self.task_id()
        self.insert_task(ext, self.rng.choice(OUTSIDE_WINDOW), self.external)
        self.live_lock(ext)
        art = self.task_id()
        self.insert_task(art, "in_dev", config.DEFAULT_TARGET)
        marker, out = self.note()
        ctx = f"внешний держатель {ext} + задача артели {art}"
        self.assertEqual(self.held_reason(marker, out, ctx),
                         f"задача {art} в состоянии in_dev",
                         f"{ctx}; зерно {self.seed}")

    def test_ac3b_earlier_external_task_does_not_mask_artel_task(self):
        """Задача внешнего проекта в `verifying` с id МЕНЬШЕ id задачи
        артели в `in_dev` (перебор по возрастанию id встречает внешнюю
        первой): запись удержана, причина — «задача <id артели> в
        состоянии in_dev».

        Ловит мутацию: первая встреченная задача окна внешнего проекта
        даёт досрочный `return None` — запись уходит в `origin` (а до
        правки причина называет внешнюю задачу)."""
        ext = self.task_id(prefix="A")
        art = self.task_id(prefix="B")
        self.assertLess(ext, art)
        self.insert_task(ext, "verifying", self.external)
        self.insert_task(art, "in_dev", config.DEFAULT_TARGET)
        marker, out = self.note()
        ctx = f"внешняя {ext} в verifying + задача артели {art}"
        self.assertEqual(self.held_reason(marker, out, ctx),
                         f"задача {art} в состоянии in_dev",
                         f"{ctx}; зерно {self.seed}")

    # --- AC-4: неизвестный проект ---

    def test_ac4_unresolved_project_holds_naming_task_and_reason(self):
        """Три случая по отдельности: (1) задача с неразрешаемым проектом
        в случайном состоянии окна; (2) живой держатель, чья задача (вне
        состояний окна) с неразрешаемым проектом; (3) живой держатель,
        строки задачи которого нет в БД. В каждом запись удержана, причина
        содержит id задачи (держателя — id его задачи) и «проект задачи не
        определён».

        Ловит мутацию: неизвестный проект молча приравнен к артели
        (`store.task_target` с умолчанием `DEFAULT_TARGET` для
        отсутствующей строки, `resolve(...) is None` трактуется как
        артель) — запись удержана прежним текстом без «проект задачи не
        определён»; либо приравнен к внешнему проекту — запись ушла в
        `origin`."""
        cases = ("задача в окне", "держатель с задачей", "держатель без строки")
        for case in cases:
            with self.subTest(case=case):
                tid = self.task_id()
                session = None
                if case == "задача в окне":
                    self.insert_task(
                        tid, self.rng.choice(config.NOTE_SILENCE_WINDOW_STATES),
                        self.ghost)
                elif case == "держатель с задачей":
                    self.insert_task(tid, self.rng.choice(OUTSIDE_WINDOW),
                                     self.ghost)
                    session = self.live_lock(tid)
                else:
                    session = self.live_lock(tid)
                marker, out = self.note()
                ctx = f"{case}: {tid}"
                reason = self.held_reason(marker, out, ctx)
                msg = f"{ctx}; причина {reason!r}; зерно {self.seed}"
                self.assertIn(tid, reason, msg)
                self.assertIn("проект задачи не определён", reason, msg)
                if session is not None:
                    store.release_merge_lock(store.db(), session, os.getpid())
                if case == "задача в окне":
                    self.set_state(tid, self.rng.choice(OUTSIDE_WINDOW))
                notes.cmd_note(["--flush"])

    # --- AC-5 ---

    def test_ac5_unresolved_project_outside_window_does_not_hold(self):
        """Задача с неразрешаемым проектом в каждом состоянии вне окна
        (`done`, `killed`, …) — других триггеров нет — `note` пушит сразу.

        Ловит мутацию: проверка проекта стоит раньше проверки состояния
        (неразрешаемый проект открывает окно в любом состоянии) — запись
        удержана с причиной «проект задачи не определён»."""
        tid = self.task_id()
        self.insert_task(tid, OUTSIDE_WINDOW[0], self.ghost)
        for state in OUTSIDE_WINDOW:
            with self.subTest(state=state):
                self.set_state(tid, state)
                marker, out = self.note()
                self.assert_pushed(marker, out,
                                   f"неразрешённая задача {tid} в {state}")


if __name__ == "__main__":
    unittest.main()
