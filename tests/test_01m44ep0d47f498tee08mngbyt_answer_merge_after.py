"""Мандат Оператора «Зависимости мержа: …» в ANSWER-n.md (AC-11, AC-12).

Группа: долгоживущий
Красен до реализации: answer строку «Зависимости мержа:» не знает и колонки merge_after в таблице tasks нет — каждый сценарий краснеет на чтении колонки (IndexError), а без неё негодная строка мандата не отказывает (ANSWER коммитится) и в merge_gate answer отказывает любому файлу.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): ссылка
документов задачи `refs/artifacts/<id>` живёт в репозитории песочницы, и
появление ANSWER-n.md в ней наблюдается по её дереву. Задачи заводятся
прямой строкой БД в состоянии сценария. Окружение роли снято переменной
`config.ARTEL_ROLE_ENV` (пустое значение); сценарий «вызов из окружения
роли» ставит её непустой. Значение колонки читается как перечень id в
порядке записи. Форма элементов (полный id или префикс), число
зависимостей и порядок вариантов — от зерна; зерно печатается и входит в
текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import answer, config, idgen, store
from tests.sandbox import RealGitSandbox

MARKER = "Зависимости мержа:"
DOCS_REF_PREFIX = "refs/artifacts/"
ARROW = re.compile(r"→|->")


def ids_of(value) -> list[str]:
    """Перечень id в значении колонки `merge_after` (пусто/NULL — пустой)."""
    return re.findall(r"[0-9A-Za-z]+", value or "")


class AnswerMandateSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        self.conn = store.db()
        self.role_env("")

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def role_env(self, value: str) -> None:
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: value})
        patcher.start()
        self.addCleanup(patcher.stop)

    def insert(self, state: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def unique_prefix(self, task_id: str) -> str:
        others = [r["id"] for r in store.all_tasks(self.conn) if r["id"] != task_id]
        shortest = next(n for n in range(1, len(task_id) + 1)
                        if not any(o.startswith(task_id[:n]) for o in others))
        return task_id[:self.rng.randint(shortest, len(task_id))]

    def element(self, task_id: str) -> str:
        return task_id if self.rng.random() < 0.5 else self.unique_prefix(task_id)

    def mandate_line(self, deps) -> str:
        """Строка мандата: `deps` — перечень задач либо `None` («нет»)."""
        if deps is None:
            return f"{MARKER} нет"
        return f"{MARKER} {', '.join(self.element(d) for d in deps)}"

    # --- команда и наблюдения ------------------------------------------------

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def deps(self, task_id: str) -> list[str]:
        return ids_of(store.get_task(self.conn, task_id)["merge_after"])

    def answers(self, task_id: str) -> list[str]:
        ref = DOCS_REF_PREFIX + task_id
        if not self.git("for-each-ref", "--format=%(objectname)", ref).strip():
            return []
        return sorted(p.rsplit("/", 1)[-1] for p in self.git(
            "ls-tree", "-r", "--name-only", ref).splitlines()
            if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def run_answer(self, task_id: str, body: str) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        source = self.root / ".artel" / f"answer-{self.rng.randrange(1 << 30)}.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"{body}\n\nОснование: решение Оператора "
                          f"({self.seed}).\n", encoding="utf-8")
        buf = io.StringIO()
        failed = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(task_id, str(source))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), failed

    def last_step_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def journal_since(self, task_id: str, since: int) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id) if r["id"] > since]

    def accepted(self, task_id: str, body: str) -> list[str]:
        """`answer` с `body` принят: ANSWER добавлен в ссылку документов;
        возврат — записи журнала, сделанные командой."""
        before = self.answers(task_id)
        since = self.last_step_id(task_id)
        out, failed = self.run_answer(task_id, body)
        self.assertFalse(failed, self.note(f"answer отказала:\n{out}"))
        self.assertEqual(len(self.answers(task_id)), len(before) + 1,
                         self.note(f"ANSWER не создан:\n{out}"))
        return self.journal_since(task_id, since)

    def assert_refused(self, task_id: str, body: str, note: str) -> None:
        """`answer` с `body` отказала до коммита: ANSWER не появился в
        ссылке документов, колонка `merge_after` прежняя."""
        before_answers = self.answers(task_id)
        before_deps = self.deps(task_id)

        out, failed = self.run_answer(task_id, body)

        context = self.note(f"{note}\nфайл: {body!r}\nвывод:\n{out}")
        self.assertTrue(failed, context)
        self.assertEqual(self.answers(task_id), before_answers, context)
        self.assertEqual(self.deps(task_id), before_deps, context)


class AnswerMandateAcceptedTest(AnswerMandateSandbox):

    def test_ac11_escalated_answer_sets_and_clears_value(self):
        """`answer` в `escalated` пишет значение строки мандата полными id, «нет» очищает.

        Сценарий: задача в `escalated` без зависимостей; ANSWER со строкой
        `Зависимости мержа:` на одну-три живые задачи (префиксами или
        полными id, от зерна) — колонка равна их полным id в порядке
        строки, запись журнала называет новые id со стрелкой «было →
        стало». Второй ANSWER со строкой `Зависимости мержа: нет` —
        колонка пуста, запись журнала называет снятые id со стрелкой.

        Ловит мутацию: строка мандата копируется в колонку как есть
        (префиксы не разрешены) либо «нет» читается как id задачи —
        колонка расходится с ожидаемой или ANSWER отказан.
        """
        task_id = self.insert("escalated")
        deps = [self.insert(self.rng.choice(["in_dev", "acceptance", "done"]))
                for _ in range(self.rng.randint(1, 3))]

        journal = self.accepted(task_id, self.mandate_line(deps))

        self.assertEqual(self.deps(task_id), deps, self.note(f"журнал: {journal}"))
        self.assertTrue([e for e in journal
                         if ARROW.search(e) and all(d in e for d in deps)],
                        self.note(f"нет записи «было → стало» с {deps}: {journal}"))

        journal = self.accepted(task_id, self.mandate_line(None))

        self.assertEqual(self.deps(task_id), [], self.note(f"журнал: {journal}"))
        self.assertTrue([e for e in journal
                         if ARROW.search(e) and all(d in e for d in deps)],
                        self.note(f"нет записи «было → стало» со снятыми "
                                  f"{deps}: {journal}"))

    def test_ac11_merge_gate_answer_outside_role_env_accepted(self):
        """В `merge_gate` ANSWER со строкой мандата принимается вне окружения роли.

        Сценарий: задача получила зависимости мандатом в `escalated`, затем
        одна из них убита, а задача стоит на `merge_gate`. ANSWER со
        строкой `Зависимости мержа:` — от зерна «нет» либо перечень
        оставшихся живых — принят: ANSWER добавлен в ссылку документов,
        колонка равна новому значению.

        Ловит мутацию: перечень принимающих состояний `answer` не дополнен
        `merge_gate` — команда отказывает «answer доступна только для
        задачи в состоянии escalated», у задачи с убитой зависимостью нет
        штатного выхода.
        """
        task_id = self.insert("escalated")
        deps = [self.insert("acceptance") for _ in range(self.rng.randint(1, 3))]
        self.accepted(task_id, self.mandate_line(deps))
        killed = self.rng.choice(deps)
        self.set_state(killed, "killed")
        self.set_state(task_id, "merge_gate")
        alive = [d for d in deps if d != killed]
        new = None if not alive or self.rng.random() < 0.5 else alive

        self.accepted(task_id, self.mandate_line(new))

        self.assertEqual(self.deps(task_id), list(new or []),
                         self.note(f"было {deps}, убита {killed}"))


class AnswerMandateRefusedTest(AnswerMandateSandbox):

    def test_ac12_invalid_mandate_element_refused_before_commit(self):
        """Строка мандата с негодной зависимостью — отказ `answer` до коммита ANSWER.

        Сценарий: для каждого варианта — своя задача в `escalated`, у части
        (от зерна) уже есть прежнее значение из живой задачи. Строка
        `Зависимости мержа:` называет несуществующий id, убитую задачу, id
        самой задачи либо задачу, чья колонка уже ведёт в эту задачу
        (цикл). `answer` завершается отказом, ANSWER-n.md в ссылке
        документов не появляется, колонка прежняя.

        Ловит мутацию: проверка правил гейта SPEC в узле мандата снята
        (проверяется только форма строки) либо стоит после коммита ANSWER —
        ANSWER появляется в ссылке документов или колонка переписана.
        """
        cases = ["нет такой задачи", "убитая", "собственная", "цикл"]
        self.rng.shuffle(cases)
        for case in cases:
            with self.subTest(case=case):
                task_id = self.insert("escalated")
                if self.rng.random() < 0.5:
                    self.accepted(task_id, self.mandate_line([self.insert("in_dev")]))
                if case == "нет такой задачи":
                    line = f"{MARKER} {idgen.new_task_id()}"
                elif case == "убитая":
                    line = self.mandate_line([self.insert("killed")])
                elif case == "собственная":
                    line = self.mandate_line([task_id])
                else:
                    other = self.insert("escalated")
                    self.accepted(other, self.mandate_line([task_id]))
                    line = self.mandate_line([other])

                self.assert_refused(task_id, line, case)

    def test_ac12_merge_gate_without_line_or_from_role_env_refused(self):
        """В `merge_gate` отказ ANSWER без строки мандата и вызова из окружения роли.

        Сценарий: задача на `merge_gate` с живой зависимостью. Первый вызов
        — файл без строки `Зависимости мержа:` вне окружения роли; второй —
        файл с годной строкой (от зерна «нет» или другая живая задача), но
        процесс в окружении роли. Оба раза `answer` отказывает, ANSWER не
        появляется в ссылке документов, колонка прежняя.

        Ловит мутацию: в `merge_gate` принимается любой ANSWER либо рубеж
        `runner.in_role_environment` для `merge_gate` не стоит — роль сама
        себе снимает зависимость мержа.
        """
        task_id = self.insert("escalated")
        self.accepted(task_id, self.mandate_line([self.insert("acceptance")]))
        self.set_state(task_id, "merge_gate")

        self.assert_refused(task_id, "Ответ: продолжай как решено.",
                            "merge_gate, файл без строки мандата")

        valid = self.mandate_line(None if self.rng.random() < 0.5
                                  else [self.insert("in_dev")])
        self.role_env(self.rng.choice(["developer", "reviewer"]))
        self.assert_refused(task_id, valid, "merge_gate, окружение роли")


if __name__ == "__main__":
    unittest.main()
