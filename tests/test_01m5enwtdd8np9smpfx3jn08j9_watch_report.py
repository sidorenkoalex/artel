"""Запись «прогон vitest» у читателей журнала: дозор относит её к классу `pytest` с общим бюджетом строк, отчёт суммирует её секунды вместе с «прогон pytest».

Группа: долгоживущий
Красен до реализации: дозор сравнивает действие только с `PYTEST_RUN_ACTION` — запись «прогон vitest» в классе `pytest` не печатается; отчёт считает секунды только записей «прогон pytest» — секунды «прогон vitest» в сумму раздела test_author не входят.

Дозор — публичный `watch.cmd_watch` с селектором `--tasks` и
`--observation` в том же потоке теста: пауза опроса подменена
(`tests.sandbox.patch_sleep`) — первая пауза дописывает в журнал записи
сценария, вторая останавливает дозор исключением; печать дозора
перехвачена. Отчёт — публичный `report.cmd_report`, раздел test_author
файла `.artel/report.html`. Числа записей — из `random`, зерно
печатается и входит в текст каждого провала; граница строк — от
`config.WATCH_PROGRESS_LINES_PER_HOUR`.

Провалидировано временным стабом реализации (удалён, не закоммичен):
сравнение действия дозора с парой `PYTEST_RUN_ACTION`/`VITEST_RUN_ACTION`
во всех трёх местах и учёт обоих действий в `report._test_author_steps` —
все методы файла зелёные.
"""
import html
import io
import random
import re
import unittest
from contextlib import redirect_stdout

from orchestrator import agent_log, config, report, session, store, watch
from tests.sandbox import SchemaTmpRootTest, patch_sleep

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
VITEST_ACTION = "прогон vitest"
PYTEST_ACTION = "прогон pytest"
ROLE = "test_author"
HEADING = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
TITLE = re.compile(r"test_author|автор\w*\s+тест", re.I)


class StopWatch(Exception):
    """Остановка дозора сценарием на второй паузе опроса."""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def text_of(chunk: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", chunk)).split())


def author_section(page: str) -> str:
    """Текст раздела отчёта, заголовок которого называет test_author."""
    headings = list(HEADING.finditer(page))
    for index, match in enumerate(headings):
        if not TITLE.search(text_of(match.group(2))):
            continue
        level = int(match.group(1))
        end = len(page)
        for later in headings[index + 1:]:
            if int(later.group(1)) <= level:
                end = later.start()
                break
        return text_of(page[match.start():end])
    return ""


class JournalSandbox(SchemaTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def new_task(self) -> str:
        task_id = ulid(self.rng)
        store.insert_task(store.db(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def vitest_detail(self) -> str:
        n = self.rng.randrange(1, 40)
        return f"{n} passed ({n}) in {self.rng.randrange(1, 90)}.{self.rng.randrange(10, 100)}s"

    def pytest_detail(self) -> str:
        return (f"{self.rng.randrange(1, 40)} passed in "
                f"{self.rng.randrange(1, 90)}.{self.rng.randrange(10, 100)}s")


class Ac7WatchTest(JournalSandbox):

    def watch_lines(self, argv: list, task_id: str, rows: list) -> list:
        """Строки дозора `argv` по записям `rows` ((действие, деталь)),
        дописанным в журнал задачи после первого опроса."""
        pauses = []

        def sleep(_seconds):
            pauses.append(_seconds)
            if len(pauses) == 1:
                for action, detail in rows:
                    store.journal(store.db(), task_id, ROLE, action, detail)
                return
            raise StopWatch()

        out = io.StringIO()
        with patch_sleep(watch, sleep), redirect_stdout(out):
            with self.assertRaises(StopWatch, msg=self.note(out.getvalue())):
                watch.cmd_watch(argv)
        return out.getvalue().splitlines()

    def selectors(self, task_id: str) -> dict:
        observation = store.register_observation(
            store.db(), config.DEFAULT_TARGET, "codex", "watch-test",
            session.resolve_session_id(None), [task_id])
        return {"--tasks": ["--tasks", task_id],
                "--observation": ["--observation", observation]}

    @staticmethod
    def shown(lines: list, task_id: str, action: str, detail: str) -> bool:
        needle = f"  {task_id}  {ROLE}  {action}  | {detail}"
        return any(line.endswith(needle) for line in lines)

    def test_ac7_watch_prints_vitest_in_pytest_class(self):
        """Дозор с классом `pytest` печатает запись «прогон vitest» строкой формата журнала; без класса `pytest` — не печатает.

        Сценарий: для селекторов `--tasks` и `--observation` после первого
        опроса в журнал задачи пишется запись «прогон vitest» со случайной
        деталью; дозор `--events pytest` печатает строку
        «<ts>  <id>  test_author  прогон vitest  | <деталь>»; дозор
        `--events steps` этой строки не печатает.

        Ловит мутацию: класс `pytest` сравнивает действие только с
        `PYTEST_RUN_ACTION` — строки «прогон vitest» нет; запись
        «прогон vitest» отнесена к классу `steps` — она печатается без
        `pytest`; сравнение пары исправлено в `--tasks`, но не в
        `--observation`.
        """
        for flag in ("--tasks", "--observation"):
            task_id = self.new_task()
            detail = self.vitest_detail()
            argv = self.selectors(task_id)[flag] + ["--events", "pytest",
                                                    "--interval", "1"]
            lines = self.watch_lines(argv, task_id, [(VITEST_ACTION, detail)])
            with self.subTest(selector=flag, events="pytest", seed=self.seed):
                self.assertTrue(self.shown(lines, task_id, VITEST_ACTION, detail),
                                self.note("\n".join(lines)))
            task_id = self.new_task()
            argv = self.selectors(task_id)[flag] + ["--events", "steps",
                                                    "--interval", "1"]
            lines = self.watch_lines(argv, task_id, [(VITEST_ACTION, detail)])
            with self.subTest(selector=flag, events="steps", seed=self.seed):
                self.assertFalse(any(f"  {VITEST_ACTION}" in line
                                     for line in lines),
                                 self.note("\n".join(lines)))

    def test_ac7_watch_shares_line_budget_of_pair(self):
        """Записи «прогон pytest» и «прогон vitest» тратят одну границу строк задачи: сверх неё «прогон vitest» не печатается.

        Сценарий: граница — `config.WATCH_PROGRESS_LINES_PER_HOUR` строк;
        после первого опроса в журнал пишется граница минус одна запись
        «прогон pytest» и затем запись «прогон vitest» — напечатаны все,
        «прогон vitest» тоже. Во втором прогоне дозора записей «прогон
        pytest» ровно граница, затем «прогон vitest» — её строки нет. Оба
        селектора: `--tasks` и `--observation`.

        Ловит мутацию: «прогон vitest» печатается мимо границы
        (`budget.take` зовётся только для «прогон pytest») — во втором
        прогоне строка есть; у «прогон vitest» своя граница — тоже есть.
        """
        limit = config.WATCH_PROGRESS_LINES_PER_HOUR
        for flag in ("--tasks", "--observation"):
            for pytest_rows, expect in ((limit - 1, True), (limit, False)):
                task_id = self.new_task()
                detail = self.vitest_detail()
                rows = [(PYTEST_ACTION, self.pytest_detail())
                        for _ in range(pytest_rows)]
                rows.append((VITEST_ACTION, detail))
                argv = self.selectors(task_id)[flag] + ["--events", "pytest",
                                                        "--interval", "1"]
                lines = self.watch_lines(argv, task_id, rows)
                with self.subTest(selector=flag, pytest_rows=pytest_rows,
                                  seed=self.seed):
                    self.assertEqual(
                        self.shown(lines, task_id, VITEST_ACTION, detail),
                        expect, self.note("\n".join(lines)))


class Ac7ReportTest(JournalSandbox):

    def test_ac7_report_sums_seconds_of_both_actions(self):
        """Раздел test_author отчёта показывает сумму секунд записей «прогон pytest» и «прогон vitest» шага.

        Сценарий: шаг test_author в окне отчёта — «agent run started»,
        несколько записей «прогон pytest» и несколько «прогон vitest» со
        случайными секундами, «agent run finished»; в тексте раздела
        test_author `report.cmd_report` стоит сумма секунд обоих действий
        с двумя знаками и не стоит сумма одних «прогон pytest».

        Ловит мутацию: `_test_author_steps` сравнивает действие только с
        `PYTEST_RUN_ACTION` — в разделе сумма без секунд Vitest; секунды
        записи «прогон vitest» читаются как 0.0 — сумма та же, что без
        них.
        """
        task_id = self.new_task()
        conn = store.db()
        log = config.LOGS / f"{task_id}-{ROLE}-1.log"
        attempt = f"попытка 1/{config.AGENT_ATTEMPTS}"
        store.journal(conn, task_id, ROLE, "agent run started",
                      f"{attempt}, model=fx-model, роль {ROLE}, источник "
                      f"модели: фикстура, лог: {log}, промпт: {log}.prompt, "
                      f"окружение: фикстура")
        pytest_sec, vitest_sec = [], []
        for _ in range(self.rng.randrange(2, 5)):
            sec = self.rng.randrange(100, 9000) / 100
            pytest_sec.append(sec)
            store.journal(conn, task_id, ROLE, agent_log.PYTEST_RUN_ACTION,
                          f"{self.rng.randrange(1, 9)} passed in {sec:.2f}s")
        for _ in range(self.rng.randrange(2, 5)):
            sec = self.rng.randrange(100, 9000) / 100
            vitest_sec.append(sec)
            n = self.rng.randrange(1, 9)
            store.journal(conn, task_id, ROLE, VITEST_ACTION,
                          f"{n} passed ({n}) in {sec:.2f}s")
        store.journal(conn, task_id, ROLE, "agent run finished",
                      f"rc=0, {attempt}, стоимость $0.5000, токенов 100, "
                      f"окружение: фикстура")
        self.capture(report.cmd_report)
        page = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        section = author_section(page)
        total = f"{sum(pytest_sec) + sum(vitest_sec):.2f}"
        only_pytest = f"{sum(pytest_sec):.2f}"
        context = self.note(f"pytest {pytest_sec}, vitest {vitest_sec}\n"
                            f"раздел:\n{section}")
        self.assertIn(f"{total} с", section, context)
        self.assertNotIn(f"{only_pytest} с", section, context)


if __name__ == "__main__":
    unittest.main()
