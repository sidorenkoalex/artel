"""AC-4: смысл теста сохранён — после `run_cmd()` сверяются ПОЛНЫЙ список
файлов каталога (без фильтра `*-wal`/`*-shm`), mtime файлов и
`COUNT(*) FROM steps` = 1.

Зелёный с рождения: все три ассерта стоят в теле теста уже сегодня
(tests/test_models.py:698-702) и фильтра служебных файлов WAL в сверке
нет — критерий охраняет их от ослабления при исправлении затравки, а не
требует нового поведения.
"""
import ast
import contextlib
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, models

import _target

# Два имени файла, который «команда» заводит в каталоге БД для
# динамической проверки. Первое — обычное, второе совпадает с шаблоном
# `*-wal`, но не с именем настоящего служебного файла SQLite: иначе
# проверка зависела бы от того, есть ли `state.db-wal` на этой платформе в
# этот момент. Оба файла обязан поймать ОДИН и тот же ассерт — сверка
# полного списка; разные ассерты означают отбор имён в сверке.
PLAIN_FILE = "sled-komandy.tmp"
WAL_SHAPED_FILE = "sled-komandy.db-wal"
ROW_COUNT_QUERY = "COUNT(*) FROM steps"
MTIME_FIELD = "st_mtime_ns"
# Приёмы фильтрации, которых в сверке списка файлов быть не должно.
FILTER_CALLS = ("endswith", "startswith", "glob", "match", "fullmatch",
                "filter", "suffix")


class Ac4SnapshotAssertsTest(unittest.TestCase):
    """AC-4: три ассерта сверки не сняты и не ослаблены."""

    @contextlib.contextmanager
    def _command_leaves(self, name: str):
        """Команда `models` дополнительно заводит файл `name` в каталоге БД
        — наблюдаемое последствие записи, которое обязан поймать полный
        список файлов.

        Каталог берётся от `config.DB` в момент вызова: его подменяет сам
        предметный тест своим временным каталогом, других адресов у планки
        нет.
        """
        real_cmd = models.cmd_models
        created: list[Path] = []

        def fake_cmd(*args, **kwargs):
            out = real_cmd(*args, **kwargs)
            path = Path(config.DB).parent / name
            path.write_text("", encoding="utf-8")
            created.append(path)
            return out

        try:
            with mock.patch.object(models, "cmd_models", fake_cmd):
                yield created
        finally:
            for path in created:
                with contextlib.suppress(OSError):
                    path.unlink()

    def _line_that_catches(self, name: str) -> int:
        """Строка тела теста, на которой он падает, если команда оставила
        после себя файл `name`."""
        with self._command_leaves(name) as created:
            result = _target.run_target()
        self.assertTrue(
            created,
            f"{_target.TARGET_NAME}: команда `models` в прогоне не звалась "
            f"через `models.cmd_models` — лишний файл завести не удалось, "
            f"проверка AC-4 в таком виде ничего не значит")
        self.assertFalse(
            result.wasSuccessful(),
            f"{_target.TARGET_NAME}: файл `{name}`, заведённый командой, тест "
            f"не заметил вовсе — сверка следов записи после `run_cmd()` снята "
            f"или обходит такие имена (AC-4)")
        report = _target.problem_reports(result)[0]
        inside = _target.lines_inside_method(report)
        self.assertTrue(
            inside,
            f"{_target.TARGET_NAME}: падение из-за файла `{name}` пришло не "
            f"на строки тела теста:\n{report}")
        return inside[-1]

    def test_ac4_unfiltered_listing_catches_a_wal_shaped_file(self):
        """Файл с именем вида `*-wal`, оставленный командой, ловится тем же
        ассертом, что и файл с обычным именем, — значит сверка списка
        файлов идёт по полному каталогу, без отбора служебных имён.

        Ловит мутацию: разработчик убрал имена `*-wal`/`*-shm` из сверки
        списка файлов (фильтром в генераторе или списком исключений), чтобы
        снять расхождение снимков на Linux. Тест при этом остаётся красным
        на обычном файле и краснеет на `*-wal` уже другим ассертом (или не
        краснеет вовсе), а ровно тот случай, ради которого тест написан —
        вызов внутри команды открыл БД по подменённому пути и оставил
        журнал, — перестаёт быть виден.
        """
        plain = self._line_that_catches(PLAIN_FILE)
        wal_shaped = self._line_that_catches(WAL_SHAPED_FILE)
        self.assertEqual(
            wal_shaped, plain,
            f"{_target.TARGET_NAME}: обычный файл `{PLAIN_FILE}` ловит строка "
            f"{plain}, а файл вида `*-wal` — строка {wal_shaped}; сверка "
            f"списка файлов вычитает служебные имена WAL, и ловит лишний "
            f"файл уже другая проверка (AC-4 требует полного списка)")

    def test_ac4_three_asserts_stay_in_the_body(self):
        """В теле остаются все три сверки после `run_cmd()` — полный список
        файлов, mtime файлов и ровно одна строка в `steps`, — а снимки
        списка берутся без условия в генераторе.

        Ловит мутацию: разработчик снял сверку mtime или ослабил проверку
        журнала (`assertGreaterEqual(rows, 1)` вместо равенства одному),
        сочтя их источником нестабильности, — тест перестал бы ловить
        запись в БД и перезапись файла тем же содержимым, хотя причина
        падений была не в них.
        """
        code = _target.body_code()
        self.assertIn(
            MTIME_FIELD, code,
            f"{_target.TARGET_NAME}: в коде теста больше нет сверки mtime "
            f"(`{MTIME_FIELD}`) — AC-4 требует сохранить её")
        self.assertIn(
            ROW_COUNT_QUERY, code,
            f"{_target.TARGET_NAME}: в коде теста больше нет запроса "
            f"`{ROW_COUNT_QUERY}` — AC-4 требует сохранить проверку журнала")

        function = _target.method_ast()
        calls = _target.assertion_calls(ast.walk(function))
        equals_one = [call for call in calls
                      if call.func.attr == "assertEqual"
                      and any(isinstance(arg, ast.Constant) and arg.value == 1
                              for arg in call.args)]
        self.assertTrue(
            equals_one,
            f"{_target.TARGET_NAME}: нет `assertEqual(..., 1)` — проверка "
            f"«в журнале ровно одна строка» снята или ослаблена до "
            f"неравенства (AC-4)")

        self.assertGreaterEqual(
            _target.iterdir_call_count(), 3,
            f"{_target.TARGET_NAME}: вызовов `iterdir()` в теле осталось "
            f"{_target.iterdir_call_count()} — сверки списка файлов и mtime "
            f"до и после `run_cmd()` требуют четырёх обходов каталога, "
            f"меньше трёх значит, что одна из сверок снята (AC-4)")

        for node in ast.walk(function):
            if not isinstance(node, (ast.GeneratorExp, ast.ListComp,
                                     ast.SetComp, ast.DictComp)):
                continue
            if "iterdir" not in _target.names_in(node):
                continue
            place = _target.absolute(node.lineno)
            filters = sorted(_target.names_in(node) & set(FILTER_CALLS))
            self.assertFalse(
                [gen.ifs for gen in node.generators if gen.ifs],
                f"{_target.TARGET_NAME}: обход каталога на строке {place} "
                f"несёт условие `if` — снимок перестал быть полным списком "
                f"файлов (AC-4 запрещает фильтр, в том числе "
                f"`*-wal`/`*-shm`)")
            self.assertFalse(
                filters,
                f"{_target.TARGET_NAME}: обход каталога на строке {place} "
                f"зовёт отбор имён ({filters}) — снимок перестал быть полным "
                f"списком файлов (AC-4)")
