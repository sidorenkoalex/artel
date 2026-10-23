"""Сбой потока чтения времени тестов не меняет полный прогон в файл лога:
ни сбой запуска потока `suite_durations.Reader`, ни сбой импорта модуля
`orchestrator.suite_durations`.

Группа: долгоживущий
Красен до реализации: ленивый импорт suite_durations в acceptance._durations_reader стоит вне try — при сбое импорта ImportError выходит из run_full_suite (сценарий 2); сценарий сбоя запуска потока зелен и до реализации — перехват исключения запуска уже есть.

Связка, которую держит тест: публичный `acceptance.run_full_suite` раннером
пульта (`command=None`) с `log=` — настоящий pytest с xdist интерпретатором
пульта по маленькому проекту во временном каталоге (песочница путей
`config` — `tests.sandbox.TmpRootTest`), поток чтения времени —
`suite_durations.Reader`. Каждый сценарий сравнивается с прогоном того же
проекта без сбоя; что прогон без сбоя оставляет файл времени, проверяется
первым (иначе сценарий холостой). Имена и число тестов проекта — от зерна;
зерно печатается и входит в текст провала.
"""
import random
import re
import string
import sys
import unittest
from pathlib import Path
from unittest import mock

import orchestrator
from orchestrator import acceptance, config, suite_durations
from tests.sandbox import TmpRootTest

LETTERS = string.ascii_lowercase
RESULT_LINE = re.compile(
    r"^(?:\[gw\d+\] \[\s*\d+%\] )?(PASSED|FAILED|ERROR|SKIPPED) (\S+::\S+)",
    re.MULTILINE)
SUMMARY_TIME = re.compile(r" in [\d.]+s$")
TRACE_SIGNS = ("Traceback (most recent call last)", "Exception in thread",
               "suite-durations")
MODULE = "orchestrator.suite_durations"


class DurationsReaderFailureTest(TmpRootTest):
    """Полный прогон с логом при сбое потока времени — как без потока."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.root_dir = self.project()
        self.run_no = 0

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def where(self, label: str) -> str:
        return f"{label}, зерно {self.seed}"

    def project(self) -> Path:
        """Проект с одним файлом тестов: 1–3 зелёных и 1–2 красных теста."""
        root = self.root / f"proj-{self.word()}"
        (root / "tests").mkdir(parents=True)
        bodies = [f"def test_ok_{self.word()}_{i}():\n    assert True\n"
                  for i in range(self.rng.randint(1, 3))]
        bodies += [f"def test_bad_{self.word()}_{i}():\n    assert 1 == 2\n"
                   for i in range(self.rng.randint(1, 2))]
        self.rng.shuffle(bodies)
        (root / "tests" / f"test_{self.word()}.py").write_text(
            "\n\n".join(bodies), encoding="utf-8")
        return root

    def run_logged(self, label: str) -> dict:
        """Один прогон `run_full_suite` раннером пульта с логом; исключение
        из прогона — провал теста с меткой сценария."""
        self.run_no += 1
        log = self.root / f"run-{self.run_no}-{self.word()}.log"
        try:
            with mock.patch.object(config, "FULL_SUITE_WORKERS", 2):
                green, output = acceptance.run_full_suite(
                    self.root_dir, extra=("-vv",), log=log,
                    limit=(120, "тест"))
        except Exception as exc:  # noqa: BLE001 — исключение и есть провал
            self.fail(f"{self.where(label)}: исключение из прогона наружу: "
                      f"{type(exc).__name__}: {exc}")
        text = log.read_bytes().decode("utf-8", errors="replace") \
            if log.is_file() else ""
        summary = SUMMARY_TIME.sub("", acceptance.run_summary_line(output))
        return {"green": green, "output": output, "log": log, "text": text,
                "summary": summary,
                "results": sorted(RESULT_LINE.findall(output)),
                "durations": suite_durations.path_for(log)}

    def plain_run(self) -> dict:
        plain = self.run_logged("без сбоя")
        where = self.where("без сбоя") + f"; вывод:\n{plain['output'][-2000:]}"
        self.assertTrue(plain["durations"].is_file(),
                        f"прогон без сбоя не оставил файла времени "
                        f"{plain['durations']} — сценарий холостой; {where}")
        self.assertFalse(plain["green"], where)
        self.assertTrue(plain["summary"], where)
        self.assertTrue(plain["results"], where)
        return plain

    def check_same(self, plain: dict, failed: dict, label: str,
                   marker: str = "") -> None:
        where = self.where(label) + f"; вывод:\n{failed['output'][-2000:]}"
        self.assertEqual(failed["green"], plain["green"], f"{where}: итог")
        self.assertEqual(failed["summary"], plain["summary"],
                         f"{where}: сводка")
        self.assertEqual(failed["results"], plain["results"],
                         f"{where}: строки результатов")
        for sign in TRACE_SIGNS + ((marker,) if marker else ()):
            self.assertNotIn(sign, failed["text"], f"{where}: «{sign}» в логе")
            self.assertNotIn(sign, failed["output"],
                             f"{where}: «{sign}» в выводе")
        self.assertFalse(failed["durations"].exists(),
                         f"{where}: файл времени {failed['durations']} есть")

    def test_ac7_reader_start_failure_keeps_run(self):
        """Запуск потока бросает RuntimeError — итог, сводка и строки результатов те же, файла времени нет.

        Проект из зелёных и красных тестов гоняется дважды: без сбоя
        (файл времени появляется) и с подменой `suite_durations.Reader.start`,
        бросающей `RuntimeError` со случайным текстом. Второй прогон не
        выпускает исключения, итог (`green`) и итоговая строка pytest без
        времени совпадают, отсортированные строки `PASSED/FAILED <id>`
        совпадают, в логе и выводе нет трассировки и текста исключения,
        файла времени рядом с логом нет.

        Ловит мутацию: убран перехват исключения при запуске потока
        (`Reader(...).start()` вне `try`) — `RuntimeError` выходит из
        `run_full_suite`, тест падает с текстом «исключение из прогона
        наружу».
        """
        plain = self.plain_run()
        marker = f"сбой-запуска-{self.word(10)}"
        with mock.patch.object(suite_durations.Reader, "start",
                               side_effect=RuntimeError(marker)):
            failed = self.run_logged("сбой запуска потока")
        self.check_same(plain, failed, "сбой запуска потока", marker)

    def test_ac7_import_failure_keeps_run(self):
        """Импорт suite_durations недоступен — итог, сводка и строки результатов те же, файла времени нет.

        Проект гоняется без сбоя (файл времени появляется), затем на время
        прогона одновременно `sys.modules["orchestrator.suite_durations"] =
        None` и снят атрибут `suite_durations` пакета `orchestrator`
        (`mock.patch.dict(orchestrator.__dict__)` с удалением ключа). Перед
        прогоном тест убеждается, что `from orchestrator import
        suite_durations` в этих условиях бросает `ImportError`. Прогон не
        выпускает исключения, итог, сводка без времени и строки результатов
        совпадают с прогоном без сбоя, трассировки в логе нет, файла времени
        нет; после блока модуль и атрибут пакета восстановлены.

        Ловит мутацию: импорт снова вне try (ленивый `from . import
        suite_durations` до `try` в `_durations_reader`) — `ImportError`
        выходит из `run_full_suite`, тест падает с текстом «исключение из
        прогона наружу».
        """
        plain = self.plain_run()
        module = sys.modules[MODULE]
        with mock.patch.dict(sys.modules, {MODULE: None}), \
                mock.patch.dict(orchestrator.__dict__):
            orchestrator.__dict__.pop("suite_durations", None)
            with self.assertRaises(ImportError,
                                   msg=self.where("сценарий холостой")):
                from orchestrator import suite_durations as probe  # noqa: F401
            failed = self.run_logged("сбой импорта")
        self.assertIs(sys.modules.get(MODULE), module,
                      self.where("sys.modules не восстановлен"))
        self.assertIs(getattr(orchestrator, "suite_durations", None), module,
                      self.where("атрибут пакета не восстановлен"))
        self.check_same(plain, failed, "сбой импорта")


if __name__ == "__main__":
    unittest.main()
