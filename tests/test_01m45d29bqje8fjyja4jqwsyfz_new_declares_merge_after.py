"""Заявление зависимостей мержа строкой ТЗ «Порядок: после …» при `new --tz` (AC-1..AC-8).

Группа: долгоживущий
Красен до реализации: new строку «Порядок: после …» не разбирает — колонка merge_after после заведения пуста и записи «merge_after заявлен Оператором» нет, негодная строка не отказывает (задача заводится), status в spec_writing/spec_gate добавки «[мерж после:» не печатает; test_ac3 зелёный с рождения (строка без «после» и ТЗ без строки уже сегодня заводят задачу без зависимостей).

Песочница — `tests.sandbox.LightTransitionSandbox`: `new` идёт штатным
`catalog.cmd_new` с файлом ТЗ во временном корне. Зависимости заводятся
либо командой `new` без ТЗ (живые задачи того же target), либо прямой
строкой `store.insert_task` там, где сценарию нужен свой id, состояние или
target. «Следы в git» наблюдаются по подменённому `subprocess.run`
песочницы (плотницкая запись ссылки документов — `commit-tree`/
`update-ref`) и по вызовам `workspace.ensure` (ветка и рабочая копия
задачи). Значение колонки читается как перечень id в порядке записи.
Форма элементов (полный id или префикс), их число и порядок, место строки
в ТЗ — от зерна; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import random
import re
import unittest
from unittest import mock

from orchestrator import catalog, config, idgen, store, workspace
from scripts import guard
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

DECLARED_ACTION = "merge_after заявлен Оператором"
NOT_CREATED = "задача не заведена"
SUFFIX_PREFIX = "[мерж после:"
WAIT_PREFIX = "[ждёт мержа:"
SHOW_MARK = "зависимости мержа"
ZONES = "orchestrator/catalog.py"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
GIT_WRITES = ("commit-tree", "update-ref")
UNFINISHED_STATES = ("spec_writing", "spec_gate", "tests_writing", "in_dev",
                     "verifying", "review", "acceptance", "merge_gate",
                     "escalated")
BAD_ELEMENTS = ("мержа «CI до ревью»", "части 1", "мержа соседней задачи",
                "волны 2")


def ids_of(value) -> list[str]:
    """Перечень id в значении колонки `merge_after` (пусто/NULL — пустой)."""
    return re.findall(r"[0-9A-Za-z]+", value or "")


class DeclaredMergeAfterSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        for rel in (ZONES, "orchestrator/fsm.py"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# фикстура\n", encoding="utf-8")
        self.conn = store.db()
        self.ensure_calls: list = []

        def ensure(task_id, branch):
            self.ensure_calls.append((task_id, branch))
            return self.wt_path, None

        patcher = mock.patch.object(workspace, "ensure", ensure)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def live_task(self) -> str:
        _, task_id = capture_new_task_id(
            catalog.cmd_new, f"Зависимость {self.rng.randrange(1 << 20)}")
        return task_id

    def insert(self, task_id: str, state: str,
               target: str = config.DEFAULT_TARGET) -> str:
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def all_ids(self) -> list[str]:
        return [r["id"] for r in store.all_tasks(self.conn)]

    def unique_prefix(self, task_id: str) -> str:
        """Префикс `task_id`, однозначный среди задач БД (длина — от зерна)."""
        others = [i for i in self.all_ids() if i != task_id]
        shortest = next(n for n in range(1, len(task_id) + 1)
                        if not any(o.startswith(task_id[:n]) for o in others))
        return task_id[:self.rng.randint(shortest, len(task_id))]

    def element(self, task_id: str) -> str:
        return task_id if self.rng.random() < 0.5 else self.unique_prefix(task_id)

    def missing_id(self) -> str:
        missing = idgen.new_task_id()
        while missing in self.all_ids():
            missing = idgen.new_task_id()
        return missing

    def tz(self, *order_lines: str, requirement: str = "Фикстура.") -> str:
        """Текст ТЗ: строки `order_lines` — перед «Зоны:» либо после неё (от
        зерна), каждая отдельным абзацем."""
        head = (f"Источник: фикстура {self.seed}.\n\nТребуется:\n"
                f"1. {requirement}\n\n")
        zones = f"Зоны: {ZONES}.\n\n"
        order = "".join(f"{line}\n\n" for line in order_lines)
        body = (head + order + zones if self.rng.random() < 0.5
                else head + zones + order)
        return body + "Не входит: прочее.\n"

    # --- команда и наблюдения ------------------------------------------------

    def run_new(self, tz_text: str) -> tuple[str, str | None]:
        """(вывод вместе с текстом отказа, id заведённой задачи либо `None` —
        `new` завершилась ненулевым `SystemExit`)."""
        path = self.root / f"tz-{self.rng.randrange(1 << 30)}.md"
        path.write_text(tz_text, encoding="utf-8")
        buf = io.StringIO()
        task_id = None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                task_id = catalog.cmd_new(
                    f"Задача {self.rng.randrange(1 << 20)}", str(path))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
                    task_id = None
        return buf.getvalue(), task_id

    def deps(self, task_id: str) -> list[str]:
        return ids_of(store.get_task(self.conn, task_id)["merge_after"])

    def journal(self, task_id: str) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id)]

    def declared(self, tz_text: str) -> str:
        """`new` с `tz_text` заводит задачу; её id."""
        out, task_id = self.run_new(tz_text)
        self.assertIsNotNone(task_id, self.note(
            f"new отказала:\n{out}\nТЗ:\n{tz_text}"))
        return task_id

    def assert_refused_without_traces(self, tz_text: str,
                                      named: list[str]) -> str:
        """`new` с `tz_text` отказывает: вывод называет каждую строку
        `named` и «задача не заведена»; новой строки задачи в БД нет, ссылка
        документов не писалась, ветка и рабочая копия не заводились."""
        rows_before = set(self.all_ids())
        git_before = len(self.git_spy.calls)
        ensure_before = len(self.ensure_calls)

        out, task_id = self.run_new(tz_text)

        context = self.note(f"ТЗ:\n{tz_text}\nвывод new:\n{out}")
        self.assertIsNone(task_id, context)
        self.assertIn(NOT_CREATED, out, context)
        for text in named:
            self.assertIn(text, out, context)
        self.assertEqual(set(self.all_ids()), rows_before, context)
        git_writes = [c for c in self.git_spy.calls[git_before:]
                      if any(w in map(str, c) for w in GIT_WRITES)]
        self.assertEqual(git_writes, [], context)
        self.assertEqual(self.ensure_calls[ensure_before:], [], context)
        return out

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def status_line(self, task_id: str) -> str:
        out = self.capture(catalog.cmd_status)
        lines = [line for line in out.splitlines() if line.startswith(task_id)]
        self.assertEqual(len(lines), 1, self.note(f"строка {task_id} в status:\n{out}"))
        return lines[0]

    def suffix(self, line: str, prefix: str) -> str | None:
        start = line.find(prefix)
        if start < 0:
            return None
        end = line.find("]", start)
        return line[start:] if end < 0 else line[start:end + 1]


class NewDeclaresTest(DeclaredMergeAfterSandbox):

    def test_ac1_order_line_declares_full_ids_in_line_order(self):
        """Строка «Порядок: после <e1>, …» — `new` пишет в колонку полные id в порядке строки и журнал.

        Сценарий: дважды — одна живая зависимость и две-три (от зерна);
        элементы — полные id или однозначные префиксы, порядок перемешан.
        `new --tz` заводит задачу; колонка `merge_after` — полные id ровно в
        порядке строки; в журнале задачи есть запись «merge_after заявлен
        Оператором», называющая каждый полный id.

        Ловит мутацию: в колонку пишется сырой хвост строки (префиксы не
        разрешены через `merge_after.check`) либо id сортируются — перечень
        колонки расходится с ожидаемым; либо запись журнала не делается —
        записи с действием нет.
        """
        for count in (1, self.rng.randint(2, 3)):
            with self.subTest(count=count):
                deps = [self.live_task() for _ in range(count)]
                self.rng.shuffle(deps)
                line = f"Порядок: после {', '.join(self.element(d) for d in deps)}"

                task_id = self.declared(self.tz(line))

                journal = self.journal(task_id)
                context = self.note(f"строка: {line}\nжурнал: {journal}")
                self.assertEqual(self.deps(task_id), deps, context)
                self.assertTrue(
                    [e for e in journal if DECLARED_ACTION in e
                     and all(d in e for d in deps)],
                    self.note(f"нет записи «{DECLARED_ACTION}» с {deps}: {context}"))

    def test_ac2_list_ends_at_parenthesis_or_dot(self):
        """Перечень кончается на «(» или «.»; текст после и следующая строка в него не входят.

        Сценарий: две живые зависимости в строке; за ними от зерна либо
        пояснение в скобках с точкой, либо точка без скобок и продолжение
        фразы. И пояснение, и следующая строка ТЗ называют ещё одну живую
        задачу — она не заявлена. Колонка — ровно две зависимости строки.

        Ловит мутацию: перечень берётся до конца строки (скобка и точка не
        режут хвост) либо разбор склеивает продолжение на следующей строке —
        `new` отказывает элементом «(пояснение …» или колонка несёт третью
        задачу.
        """
        deps = [self.live_task() for _ in range(2)]
        other = self.live_task()
        listed = ", ".join(self.element(d) for d in deps)
        if self.rng.random() < 0.5:
            line = (f"Порядок: после {listed} (зона {ZONES}, рядом {other}, "
                    f"ждать его).\nпродолжение: {other}, затем прочее")
        else:
            line = (f"Порядок: после {listed}. Потом {other}, если успеем\n"
                    f"{other}, ещё строка")

        task_id = self.declared(self.tz(line))

        self.assertEqual(self.deps(task_id), deps, self.note(f"строка:\n{line}"))

    def test_ac3_order_line_without_after_declares_nothing(self):
        """«Порядок: без зависимостей», «Порядок: первая, без зависимостей» и ТЗ без строки — без зависимостей.

        Сценарий: три варианта ТЗ; в каждом пункт «Требуется» упоминает
        «после <id живой задачи>» обычным текстом. Задача заводится,
        колонка `merge_after` пуста, записи «merge_after заявлен
        Оператором» в журнале нет.

        Ловит мутацию: хвост «Порядок:» разбирается перечнем и без слова
        «после» (отказ «без зависимостей» не id) либо «после <id>» ищется
        по всему ТЗ, а не в строке с меткой с первой позиции — колонка
        непуста.
        """
        live = self.live_task()
        variants = [("Порядок: без зависимостей",),
                    ("Порядок: первая, без зависимостей",), ()]
        self.rng.shuffle(variants)
        for lines in variants:
            with self.subTest(lines=lines):
                tz_text = self.tz(*lines, requirement=f"Сделать после {live}.")

                task_id = self.declared(tz_text)

                journal = self.journal(task_id)
                context = self.note(f"ТЗ:\n{tz_text}\nжурнал: {journal}")
                self.assertEqual(self.deps(task_id), [], context)
                self.assertFalse([e for e in journal if DECLARED_ACTION in e],
                                 context)


class NewRefusesTest(DeclaredMergeAfterSandbox):

    def test_ac4_unparsed_element_refused_without_traces(self):
        """Элемент хвоста, не являющийся id по форме, — отказ `new` с его названием и без следов.

        Сценарий: хвост строки — неразобранный элемент (от зерна, например
        «мержа «CI до ревью»»), от зерна рядом с годной живой
        зависимостью. Вывод `new` называет элемент и «задача не заведена»;
        строки задачи в БД нет, ссылка документов не писалась, ветка не
        заводилась.

        Ловит мутацию: негодный элемент молча отбрасывается и задача
        заводится с остальными (или без зависимостей) либо проверка стоит
        после заведения строки — в БД появляется задача.
        """
        bad = self.rng.choice(BAD_ELEMENTS)
        items = [bad]
        if self.rng.random() < 0.5:
            items.append(self.element(self.live_task()))
            self.rng.shuffle(items)

        self.assert_refused_without_traces(
            self.tz(f"Порядок: после {', '.join(items)}"), [bad])

    def test_ac5_repeated_order_line_refused_without_traces(self):
        """Две строки «Порядок: после …» в одном ТЗ — отказ `new` с причиной повтора.

        Сценарий: обе строки годны (по живой зависимости, от зерна — одной и
        той же или разным). `new` отказывает, вывод называет повтор строки
        и «задача не заведена»; следов в БД и git нет.

        Ловит мутацию: значения строк объединяются или берётся первая
        строка — задача заводится.
        """
        first = self.live_task()
        second = first if self.rng.random() < 0.5 else self.live_task()
        tz_text = self.tz(f"Порядок: после {self.element(first)}",
                          f"Порядок: после {self.element(second)}")

        out = self.assert_refused_without_traces(tz_text, [])

        self.assertRegex(out, re.compile(r"повтор", re.IGNORECASE),
                         self.note(out))

    def test_ac6_invalid_dependency_refused_without_traces(self):
        """Несуществующий, неоднозначный, убитый, чужого target или повторённый элемент — отказ `new`.

        Сценарий: для каждого варианта (порядок — от зерна) строка
        «Порядок: после …» несёт негодный элемент. Вывод `new` называет
        элемент, причину и «задача не заведена»; новой строки задачи в БД
        нет, ссылка документов не писалась, ветка не заводилась.

        Ловит мутацию: строка разбирается только по форме, без
        `merge_after.check` по БД (задача заводится), либо target заводимой
        задачи берётся из несуществующей строки БД/не сверяется — чужой
        target проходит, либо проверка стоит после заведения строки.
        """
        cases = ["нет такой задачи", "неоднозначный префикс", "убитая",
                 "чужой target", "повтор"]
        self.rng.shuffle(cases)
        for case in cases:
            with self.subTest(case=case):
                if case == "нет такой задачи":
                    element = self.missing_id()
                    items, reason = [element], r"нет такой задачи"
                elif case == "неоднозначный префикс":
                    base = idgen.new_task_id()
                    element = base[:self.rng.randint(12, 20)]
                    for tail in self.rng.sample(CROCKFORD, 2):
                        self.insert(element + tail
                                    + base[len(element) + 1:], "in_dev")
                    items, reason = [element], r"неоднознач"
                elif case == "убитая":
                    dep = self.insert(idgen.new_task_id(), "killed")
                    element = self.element(dep)
                    items, reason = [element], r"killed|убит"
                elif case == "чужой target":
                    dep = self.insert(idgen.new_task_id(),
                                      self.rng.choice(["in_dev", "done"]),
                                      target=f"proekt{self.rng.randrange(1 << 20)}")
                    element = self.element(dep)
                    items, reason = [element], r"target|проект"
                else:
                    dep = self.live_task()
                    element = self.unique_prefix(dep)
                    items, reason = [dep, element], r"повтор"
                    self.rng.shuffle(items)

                out = self.assert_refused_without_traces(
                    self.tz(f"Порядок: после {', '.join(items)}"), [element])

                self.assertRegex(out, re.compile(reason, re.IGNORECASE),
                                 self.note(out))

    def test_ac7_path_refusal_and_order_refusal_printed_together(self):
        """ТЗ с путём вне зон и негодной строкой «Порядок: после …» — обе причины одним вызовом `new`.

        Сценарий: пункт «Требуется» называет существующий путь вне «Зоны:»;
        строка «Порядок: после …» несёт (от зерна) элемент не в форме id
        либо id несуществующей задачи. Вывод одного вызова `new` называет
        и путь с подсказкой сверки путей, и негодный элемент; задача не
        заведена.

        Ловит мутацию: отказ сверки путей выходит раньше разбора строки
        «Порядок:» (или наоборот) — Оператор видит одну причину из двух.
        """
        element = (self.rng.choice(BAD_ELEMENTS) if self.rng.random() < 0.5
                   else self.missing_id())
        tz_text = self.tz(f"Порядок: после {element}",
                          requirement="Починить orchestrator/fsm.py.")

        self.assert_refused_without_traces(
            tz_text, ["orchestrator/fsm.py", guard.UNCLASSIFIED_PATH_HINT,
                      element])


class DeclaredStatusShowTest(DeclaredMergeAfterSandbox):

    def test_ac8_status_and_show_carry_declared_dependencies(self):
        """Сразу после `new` `status` в `spec_writing`/`spec_gate` несёт «[мерж после: …]», `show` — строку зависимостей.

        Сценарий: одна-две заявленные зависимости в незавершённых
        состояниях (от зерна). `show` сразу после `new` печатает строку
        зависимостей мержа с каждым id. `status` в `spec_writing` и затем в
        `spec_gate` печатает в строке задачи добавку `[мерж после: …]`, где
        каждая зависимость названа как `<id> (<состояние>)`, и не печатает
        `[ждёт мержа:`. После перевода всех зависимостей в `done` добавки
        нет.

        Ловит мутацию: добавка печатается только в `acceptance`/`merge_gate`
        (нет в ранних состояниях) либо вместо неё расширено
        `[ждёт мержа:`; либо состояние зависимости кэшируется и не читается
        из БД на каждый вызов — добавка остаётся после `done`.
        """
        deps = {self.live_task(): self.rng.choice(UNFINISHED_STATES)
                for _ in range(self.rng.randint(1, 2))}
        for dep, state in deps.items():
            self.set_state(dep, state)
        line = f"Порядок: после {', '.join(self.element(d) for d in deps)}"
        task_id = self.declared(self.tz(line))

        out = self.capture(catalog.cmd_show, task_id)
        shown = [s for s in out.splitlines() if SHOW_MARK in s.lower()]
        self.assertTrue(shown and all(d in shown[0] for d in deps),
                        self.note(f"show:\n{out}"))

        for task_state in ("spec_writing", "spec_gate"):
            self.set_state(task_id, task_state)
            row = self.status_line(task_id)
            suffix = self.suffix(row, SUFFIX_PREFIX)
            context = self.note(f"{task_state}: {row}")
            self.assertIsNotNone(suffix, context)
            for dep, state in deps.items():
                self.assertIn(f"{dep} ({state})", suffix, context)
            self.assertIsNone(self.suffix(row, WAIT_PREFIX), context)

        for dep in deps:
            self.set_state(dep, "done")
        row = self.status_line(task_id)

        self.assertIsNone(self.suffix(row, SUFFIX_PREFIX), self.note(
            f"добавка осталась после перевода зависимостей в done: {row}"))


if __name__ == "__main__":
    unittest.main()
