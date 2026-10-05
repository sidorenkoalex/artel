"""Зависимости мержа в выводе `status` и `show` (AC-13, AC-14).

Группа: долгоживущий
Красен до реализации: колонки merge_after в таблице tasks нет и гейт SPEC значение не записывает — сценарии с зависимостями краснеют на предпосылке «значение записано гейтом SPEC» (IndexError), а status/show зависимостей не печатают; test_ac14 без зависимостей и ветвь «поля нет» test_ac13 зелёные с рождения.

Песочница — `tests.sandbox.LightTransitionSandbox`. Значение `merge_after`
задача получает штатным `approve` гейта SPEC (SPEC.md на диске
`config.TASKS/<id>/`), затем задаче и зависимостям выставляются состояния
сценария прямой правкой строки БД. Строка задачи в `status` — строка
вывода, начинающаяся с её id; добавка — подстрока от `[ждёт мержа:` до
закрывающей скобки. Число зависимостей, их состояния, состояние задачи и
форма элементов SPEC — от зерна; зерно печатается и входит в текст каждого
провала.
"""
import random
import re
import unittest

from orchestrator import catalog, config, fsm, store
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/catalog.py
budget_usd: 30
{field_line}---

# SPEC: фикстура вывода зависимостей

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.
"""

WAIT_PREFIX = "[ждёт мержа:"
SHOW_PREFIX = "зависимости мержа:"
UNFINISHED_STATES = ("spec_gate", "tests_writing", "in_dev", "verifying",
                     "review", "acceptance", "merge_gate", "escalated")
WAITING_STATES = ("acceptance", "merge_gate")
OTHER_STATES = ("spec_writing", "tests_writing", "in_dev", "verifying",
                "review", "escalated")


def ids_of(value) -> list[str]:
    return re.findall(r"[0-9A-Za-z]+", value or "")


class DependencyOutputSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        path = self.root / "orchestrator" / "catalog.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")
        self.conn = store.db()

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def new_task(self) -> str:
        _, task_id = capture_new_task_id(catalog.cmd_new,
                                         f"Задача {self.rng.randrange(1 << 20)}")
        return task_id

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def element(self, task_id: str) -> str:
        others = [r["id"] for r in store.all_tasks(self.conn) if r["id"] != task_id]
        shortest = next(n for n in range(1, len(task_id) + 1)
                        if not any(o.startswith(task_id[:n]) for o in others))
        return task_id[:self.rng.randint(shortest, len(task_id))]

    def with_dependencies(self, task_id: str, deps) -> None:
        """`approve` гейта SPEC с `merge_after: deps` (`None` — без поля)."""
        field_line = ("" if deps is None else
                      f"merge_after: {', '.join(self.element(d) for d in deps)}\n")
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_TEXT.format(task=task_id, field_line=field_line), encoding="utf-8")
        self.set_state(task_id, "spec_gate")
        out = self.capture(fsm.cmd_approve, task_id)
        self.assertNotEqual(store.get_task(self.conn, task_id)["state"],
                            "spec_gate", self.note(f"предпосылка:\n{out}"))
        if deps is None:
            return
        self.assertEqual(ids_of(store.get_task(self.conn, task_id)["merge_after"]),
                         deps, self.note(
                             f"предпосылка: approve гейта SPEC не записал "
                             f"merge_after {deps}:\n{out}"))

    def status_line(self, task_id: str) -> str:
        out = self.capture(catalog.cmd_status)
        lines = [line for line in out.splitlines() if line.startswith(task_id)]
        self.assertEqual(len(lines), 1, self.note(f"строка {task_id} в status:\n{out}"))
        return lines[0]

    def wait_suffix(self, line: str) -> str | None:
        start = line.find(WAIT_PREFIX)
        if start < 0:
            return None
        end = line.find("]", start)
        return line[start:] if end < 0 else line[start:end + 1]

    def dependency_scenario(self) -> tuple[str, dict, list[str]]:
        """Задача с одной-тремя зависимостями: {незавершённая: состояние}
        (хотя бы одна) и перечень завершённых (`done`)."""
        task_id = self.TASK
        unfinished = {self.new_task(): self.rng.choice(UNFINISHED_STATES)
                      for _ in range(self.rng.randint(1, 2))}
        done = [self.new_task() for _ in range(self.rng.randint(0, 1))]
        deps = list(unfinished) + done
        self.rng.shuffle(deps)
        self.with_dependencies(task_id, deps)
        for dep, state in unfinished.items():
            self.set_state(dep, state)
        for dep in done:
            self.set_state(dep, "done")
        return task_id, unfinished, done


class StatusSuffixTest(DependencyOutputSandbox):

    def test_ac13_status_suffix_lists_unfinished_and_disappears_after_done(self):
        """Задача в `acceptance`/`merge_gate` с незавершёнными зависимостями несёт добавку `[ждёт мержа: …]`.

        Сценарий: одна-две незавершённые зависимости (состояния от зерна) и
        от нуля до одной в `done`; задача в `acceptance` или `merge_gate`.
        Строка задачи в `status` заканчивается добавкой, в которой каждая
        незавершённая названа как `<id> (<состояние>)`, а завершённой нет.
        Затем все зависимости переводятся в `done` правкой БД — следующий
        `status` печатает строку без добавки.

        Ловит мутацию: добавка строится один раз и кэшируется (не из БД на
        каждый вызов) либо включает и завершённые зависимости — после
        перевода в `done` добавка остаётся или называет завершённую.
        """
        task_id, unfinished, done = self.dependency_scenario()
        self.set_state(task_id, self.rng.choice(WAITING_STATES))

        line = self.status_line(task_id)

        suffix = self.wait_suffix(line)
        self.assertIsNotNone(suffix, self.note(f"нет добавки: {line}"))
        self.assertTrue(line.rstrip().endswith(suffix), self.note(
            f"добавка не в конце строки: {line}"))
        for dep, state in unfinished.items():
            self.assertIn(f"{dep} ({state})", suffix, self.note(line))
        for dep in done:
            self.assertNotIn(dep, suffix, self.note(line))

        for dep in unfinished:
            self.set_state(dep, "done")
        line = self.status_line(task_id)

        self.assertIsNone(self.wait_suffix(line), self.note(
            f"добавка осталась после перевода зависимостей в done: {line}"))

    def test_ac13_no_suffix_in_other_state(self):
        """Задача вне `acceptance`/`merge_gate` добавки не несёт даже с незавершёнными зависимостями.

        Сценарий: одна-две незавершённые зависимости; задача в одном из
        прочих рабочих состояний (от зерна, например `in_dev`). Строка
        задачи в `status` без `[ждёт мержа:`.

        Ловит мутацию: фильтр состояния задачи снят — добавка печатается в
        любом состоянии.
        """
        task_id, _, _ = self.dependency_scenario()
        self.set_state(task_id, self.rng.choice(OTHER_STATES))

        line = self.status_line(task_id)

        self.assertIsNone(self.wait_suffix(line), self.note(line))

    def test_ac13_no_suffix_without_field_or_all_done(self):
        """Без поля `merge_after` и со всеми зависимостями в `done` добавки нет.

        Сценарий: задача в `acceptance`/`merge_gate` (от зерна) — от зерна
        либо SPEC без поля (в БД при этом есть незавершённые посторонние
        задачи), либо одна-две зависимости, все в `done`. Строка задачи в
        `status` без `[ждёт мержа:`.

        Ловит мутацию: условие «есть зависимости не в done» снято
        (добавка печатается для любой непустой колонки) либо пустая
        колонка читается как «ждём всех» — добавка с пустым или чужим
        перечнем.
        """
        task_id = self.TASK
        if self.rng.random() < 0.5:
            for _ in range(self.rng.randint(1, 2)):
                self.set_state(self.new_task(), self.rng.choice(UNFINISHED_STATES))
            self.with_dependencies(task_id, None)
        else:
            deps = [self.new_task() for _ in range(self.rng.randint(1, 2))]
            self.with_dependencies(task_id, deps)
            for dep in deps:
                self.set_state(dep, "done")
        self.set_state(task_id, self.rng.choice(WAITING_STATES))

        line = self.status_line(task_id)

        self.assertIsNone(self.wait_suffix(line), self.note(line))


class ShowDependenciesTest(DependencyOutputSandbox):

    def test_ac14_show_lists_all_dependencies_with_states(self):
        """`show` задачи с непустым `merge_after` печатает строку со всеми зависимостями и их состояниями.

        Сценарий: незавершённые и завершённые (`done`) зависимости, задача в
        любом состоянии (от зерна). Вывод `show` несёт строку
        `зависимости мержа:`, в которой каждая зависимость названа как
        `<id> (<состояние>)`, включая `done`.

        Ловит мутацию: `show` переиспользует фильтр добавки `status` —
        зависимости в `done` в строке нет.
        """
        task_id, unfinished, done = self.dependency_scenario()
        if not done:
            extra = self.new_task()
            self.with_dependencies(task_id, list(unfinished) + [extra])
            self.set_state(extra, "done")
            done = [extra]
        self.set_state(task_id, self.rng.choice(WAITING_STATES + OTHER_STATES))

        out = self.capture(catalog.cmd_show, task_id)

        lines = [line for line in out.splitlines() if SHOW_PREFIX in line]
        self.assertEqual(len(lines), 1, self.note(out))
        for dep, state in list(unfinished.items()) + [(d, "done") for d in done]:
            self.assertIn(f"{dep} ({state})", lines[0], self.note(out))

    def test_ac14_show_without_dependencies_has_no_line(self):
        """У задачи без зависимостей строки `зависимости мержа:` в `show` нет.

        Сценарий: SPEC без поля; в БД есть посторонние задачи; задача в
        любом состоянии (от зерна). В выводе `show` строки нет.

        Ловит мутацию: строка печатается безусловно (с пустым перечнем
        или «—»).
        """
        for _ in range(self.rng.randint(1, 2)):
            self.new_task()
        self.with_dependencies(self.TASK, None)
        self.set_state(self.TASK, self.rng.choice(WAITING_STATES + OTHER_STATES))

        out = self.capture(catalog.cmd_show, self.TASK)

        self.assertNotIn(SHOW_PREFIX, out.lower(), self.note(out))


if __name__ == "__main__":
    unittest.main()
