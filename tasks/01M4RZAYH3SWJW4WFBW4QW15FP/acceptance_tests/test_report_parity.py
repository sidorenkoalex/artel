"""Сверки задачи с соседями: регулярное выражение пути лога и отчёт базы.

Здесь — то, что сверяется с закрытым именем соседнего модуля
(`report._LOG_PATH_RE`) или с версией `orchestrator/report.py` на базе
ветки задачи (`_pult.DIFF_BASE`): долгоживущим файлам `tests/` закрытые
имена и git недоступны, а «HTML остальных блоков не изменился» — разница
ветки с базой, факт этой задачи. Поведение сводки, команды и блока держат
долгоживущие файлы `tests/test_01m4rzayh3swjw4wfbw4qw15fp_*.py`.

Группа: разовый
Красен до реализации: модуля orchestrator/explore_metric.py нет — импорт в test_ac1 падает ModuleNotFoundError; блока «Разведка ролей» в отчёте нет — test_ac15 не находит его секцию.
"""
import contextlib
import importlib
import io
import re
import subprocess
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import config, report, store  # noqa: E402
from orchestrator.providers import claude  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

BLOCK_MARK = "Разведка ролей"

# AC-15 по ANSWER-1: часть «число запросов к steps не растёт с числом задач»
# снята; «store.db() один раз и запросов к steps столько же, сколько с
# заглушкой функции блока, на 2 и на 7 задачах» держит долгоживущий
# test_ac15_block_adds_no_steps_query_at_any_task_count.


class LogPathRegexTest(unittest.TestCase):
    """AC-1: регулярное выражение пути лога модуля и `report._LOG_PATH_RE`."""

    def test_ac1_log_path_regex_parses_like_report(self):
        """Запись «agent run started» с путём лога, несущим пробел и запятую.

        В модуле сводки объявлено регулярное выражение тем же текстом и
        с теми же флагами, что `report._LOG_PATH_RE`; оба выделяют из
        записи один и тот же путь.

        Ловит мутацию: в модуле объявлен иной текст выражения (например,
        `лог: (\\S+)` или жадное `(.+)`) — выражения с текстом
        `report._LOG_PATH_RE` в модуле не найдётся, а путь с пробелом и
        запятой разберётся иначе.
        """
        explore_metric = importlib.import_module("orchestrator.explore_metric")
        reference = report._LOG_PATH_RE
        own = [value for value in vars(explore_metric).values()
               if isinstance(value, re.Pattern)
               and value.pattern == reference.pattern]
        self.assertTrue(own, "в модуле нет выражения с текстом report._LOG_PATH_RE")
        detail = ("попытка 1/3, model=m, роль developer, лог: /Users/op/логи "
                  "шагов, архив/T1-developer-1.log, промпт: /Users/op/p 1.md, "
                  "окружение: x")
        expected = reference.search(detail).group(1)
        self.assertIn(", ", expected)
        for pattern in own:
            self.assertEqual(reference.flags, pattern.flags)
            self.assertEqual(expected, pattern.search(detail).group(1))


class OtherBlocksUnchangedTest(SchemaConnTmpRootTest):
    """AC-15: HTML остальных блоков отчёта не меняется."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_source = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "show",
             f"{DIFF_BASE}:orchestrator/report.py"],
            capture_output=True, text=True, check=True).stdout

    def base_report(self):
        """Модуль `report` базы ветки в пакете `orchestrator` текущей копии."""
        module = types.ModuleType("orchestrator.report_base_plank")
        module.__package__ = "orchestrator"
        module.__file__ = str(Path(CODE_ROOT) / "orchestrator" / "report.py")
        exec(compile(self.base_source, "base:orchestrator/report.py", "exec"),
             module.__dict__)
        return module

    def seed(self) -> None:
        now = datetime.now(timezone.utc)
        logs = Path(config.LOGS)
        logs.mkdir(parents=True, exist_ok=True)
        for k, (state, role) in enumerate((("in_dev", "developer"),
                                           ("tests_writing", "test_author"),
                                           ("done", "reviewer"))):
            tid = f"T{k + 101}"
            store.insert_task(self.conn, tid, f"Задача {k}", state,
                              f"task/{tid.lower()}", config.DEFAULT_TARGET, 25.0)
            log = logs / f"{tid}-{role}-1.log"
            log.write_text(
                f"{claude.TOOL_CALL_LINE_PREFIX}Read wt:orchestrator/a{k}.py\n"
                f"{claude.TOOL_CALL_LINE_PREFIX}Write wt:tests/test_a{k}.py\n",
                encoding="utf-8")
            for ago, actor, action, detail in (
                    (timedelta(hours=5), role, "agent run started",
                     f"попытка 1/1, model=m, лог: {log}, промпт: {logs}/p.md, "
                     "окружение: x"),
                    (timedelta(hours=4), "operator", "state -> merge_gate", "гейт"),
                    (timedelta(days=2), "operator", "approve", "приёмка")):
                self.conn.execute(
                    "INSERT INTO steps (task_id, target, ts, actor, action, "
                    "detail, session_id) VALUES (?,?,?,?,?,?,?)",
                    (tid, config.DEFAULT_TARGET,
                     (now - ago).strftime("%Y-%m-%d %H:%M:%SZ"), actor, action,
                     detail, "fixture"))
        self.conn.commit()

    def render(self, module) -> tuple:
        """(HTML, запросов к `steps`) прогона `cmd_report` модуля на одном
        соединении песочницы, которое вызывающий не закрывает."""
        conn = self.conn
        statements = []

        class Borrowed:
            def __getattr__(self, name):
                return getattr(conn, name)

            def close(self):
                return None

            def __enter__(self):
                return conn.__enter__()

            def __exit__(self, *exc_info):
                return conn.__exit__(*exc_info)

        def trace(statement):
            if statement and re.search(r"\bfrom\s+steps\b", str(statement), re.I):
                statements.append(statement)

        conn.set_trace_callback(trace)
        try:
            with mock.patch.object(store, "db", lambda: Borrowed()), \
                    contextlib.redirect_stdout(io.StringIO()):
                module.cmd_report()
        finally:
            conn.set_trace_callback(None)
        page = (Path(config.ROOT) / ".artel" / "report.html").read_text(
            encoding="utf-8")
        return page, len(statements)

    def test_ac15_other_report_blocks_unchanged(self):
        """Один и тот же журнал песочницы отрисован отчётом базы ветки и
        отчётом ветки.

        В отчёте ветки ровно одна секция «Разведка ролей»; без неё
        последовательность секций совпадает с отчётом базы символ в символ;
        запросов к `steps` за прогон столько же, сколько у отчёта базы.

        Ловит мутацию: блок разведки встроен в чужую секцию или задел её
        разметку (например, окно заголовка test_author сменилось на 7 дней
        вслед за константой блока) — секции ветки без блока разойдутся с
        секциями базы; блок перечитывает журнал сам (`store.
        steps_of_action`/`all_steps` в `cmd_report`) — запросов к `steps`
        станет больше, чем у базы.
        """
        self.seed()
        base_page, base_queries = self.render(self.base_report())
        page, queries = self.render(report)

        self.assertEqual(base_queries, queries, "запросов к steps у базы и ветки")
        sections = re.findall(r"<section\b.*?</section>", page, re.S)
        base_sections = re.findall(r"<section\b.*?</section>", base_page, re.S)
        explore = [s for s in sections if BLOCK_MARK in s]
        self.assertEqual(1, len(explore), "секции «Разведка ролей» нет или их несколько")
        self.assertEqual(base_sections,
                         [s for s in sections if BLOCK_MARK not in s])


if __name__ == "__main__":
    unittest.main()
