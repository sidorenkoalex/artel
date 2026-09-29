"""AC-5..AC-9 — выход из `tests_writing` задачи target `artel`: дифф
кодовой ветки против базы несёт только добавленные файлы
`tests/test_<префикс>_<имя>.py` со строкой `Группа: долгоживущий`,
путь которых не существует в `origin/main`; к каждому такому файлу
применяются проверки задачи 1 (статические признаки, «Ловит мутацию»,
сухой сбор); долгоживущий файл в каталоге приёмочных тестов даёт отказ с
подсказкой перенести его в `tests/`.

Отказ наблюдается так: задача осталась в `tests_writing`, и текст отказа
(запись журнала за этот `advance` либо его вывод) называет путь. Имя
действия журнала SPEC не фиксирует.

Контроль каждого сценария — тот же `advance` на чистом долгоживущем файле
с префиксом проходит в `in_dev`: отказ вызван нарушением, а не песочницей.

Группа: разовый
Красен до реализации: гейта «только добавление» на выходе из `tests_writing` ещё нет — дифф кодовой ветки не читается, файлы `tests/` не проверяются, и каждый сценарий нарушения уходит в `in_dev`; долгоживущий файл в каталоге приёмочных тестов сегодня законен (временная оговорка задачи 1).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

# «tests/» как самостоятельный путь, не хвост `acceptance_tests/`.
TESTS_DIR = re.compile(r"(?<![\w/])tests/")


class TestsWritingGateTest(_sandbox.LongLivedSandbox):

    def assert_refused(self, *needles: str, why: str) -> str:
        """`advance` из `tests_writing` отклонён, и текст отказа несёт все
        `needles`. Возвращает текст отказа."""
        out, entries = self.exit_tests_writing()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "tests_writing",
                         f"{why}: переход обязан быть отклонён; {text}")
        self.assertTrue(_sandbox.mentions(text, *needles),
                        f"{why}: отказ не называет {needles!r}: {text}")
        return text

    def assert_passes(self, why: str) -> None:
        out, entries = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev",
                         f"{why}: переход обязан пройти: {entries!r}\n{out}")

    def test_ac5_diff_with_m_d_r_foreign_or_outside_paths_is_refused(self):
        """Пять сценариев поверх чистого долгоживущего файла задачи: правка
        (`M`), удаление (`D`), переименование (`R`) файла базы
        `tests/test_existing.py`, добавленный `tests/test_noprefix.py`
        (без префикса), добавленный `docs/extra.md` (вне `tests/`). Каждый
        отклоняет выход, и отказ называет путь нарушения; без нарушения
        тот же выход проходит.

        Ловит мутацию: гейт разбирает `git diff --name-only` вместо
        `--name-status` и проверяет только префикс имени — правка и
        удаление файла базы (`M`/`D`) проходят, как и переименование в имя
        с префиксом.
        """
        good = self.ll_path("alpha")
        existing = "tests/test_existing.py"
        with self.subTest(scenario="контроль"):
            self.wt_commit({good: _sandbox.long_lived_source()})
            self.assert_passes("чистый долгоживущий файл")

        scenarios = {
            "M": (lambda: self.wt_commit({
                existing: self.branch_text(existing) + "# правка\n"}),
                existing),
            "D": (lambda: self.wt_commit(remove=[existing]), existing),
            "R": (lambda: self.wt_commit(
                rename=(existing, self.ll_path("renamed"))), existing),
            "без префикса": (lambda: self.wt_commit({
                "tests/test_noprefix.py": _sandbox.long_lived_source()}),
                "tests/test_noprefix.py"),
            "вне tests/": (lambda: self.wt_commit({
                "docs/extra.md": "# вне tests/\n"}), "docs/extra.md"),
        }
        for label, (make, path) in scenarios.items():
            with self.subTest(scenario=label):
                self.reset_branch()
                self.wt_commit({good: _sandbox.long_lived_source()})
                make()
                if label == "R":
                    text = self.assert_refused(why=label)
                    self.assertTrue(
                        path in text or self.ll_path("renamed") in text,
                        f"R: отказ не называет ни старый, ни новый путь: {text}")
                else:
                    self.assert_refused(path, why=label)

    def test_ac6_path_existing_in_origin_main_is_refused(self):
        """Ветка задачи добавила `tests/test_<префикс>_twin.py`, а тот же
        путь после ответвления появился в `origin/main` — в диффе против
        базы это по-прежнему `A`, но выход отклонён, и отказ называет путь.

        Ловит мутацию: «путь уже есть» проверяется по дереву базы ветки
        (`git cat-file -e <база>:<путь>`), а не по `origin/main` — в базе
        пути нет, и переход проходит.
        """
        rel = self.ll_path("twin")
        self.push_main_file(rel, _sandbox.long_lived_source(tag="main"))
        self.wt_commit({rel: _sandbox.long_lived_source(tag="ветка")})
        self.assert_refused(rel, why="путь уже в origin/main")

    def test_ac7_added_prefixed_file_without_long_lived_line_is_refused(self):
        """Добавленный файл с префиксом, чья строка группы — `разовый`, и
        файл вовсе без строки группы: каждый отклоняет выход, и отказ
        называет путь.

        Ловит мутацию: проверка группы файлов `tests/` принимает любую
        распознанную строку группы (`разовый` тоже) — разовый файл уезжает
        в `tests/` и живёт после мержа.
        """
        rel = self.ll_path("group")
        once = _sandbox.long_lived_source(group="разовый")
        no_line = _sandbox.long_lived_source().replace(
            "Группа: долгоживущий\n", "")
        for label, text in (("разовый", once), ("без строки", no_line)):
            with self.subTest(scenario=label):
                self.reset_branch()
                self.wt_commit({rel: text})
                self.assert_refused(rel, why=label)

    def test_ac8_task1_checks_apply_to_long_lived_file_in_tests(self):
        """Три нарушения в долгоживущем файле `tests/` задачи — признак
        `sys.path`, метод без «Ловит мутацию», модуль, падающий при
        импорте (не собирается), — каждое отклоняет выход; тот же файл
        без нарушения проходит.

        Ловит мутацию: проверки задачи 1 подключены только к каталогу
        приёмочных тестов (`guard.acceptance_test_files(acc_tdir)`), а
        файлы `tests/` кодовой ветки ими не читаются — все три нарушения
        проходят.
        """
        rel = self.ll_path("checks")
        with self.subTest(scenario="контроль"):
            self.wt_commit({rel: _sandbox.long_lived_source()})
            self.assert_passes("чистый долгоживущий файл")
        scenarios = {
            "признак sys.path": _sandbox.long_lived_source(
                body='import sys\nsys.path.insert(0, "/nonexistent")\n'),
            "нет «Ловит мутацию»": _sandbox.long_lived_source(
                claim="Без заявки."),
            "не собирается": _sandbox.long_lived_source(
                body='raise RuntimeError("фикстура не собирается")\n'),
        }
        for label, text in scenarios.items():
            with self.subTest(scenario=label):
                self.reset_branch()
                self.wt_commit({rel: text})
                self.assert_refused(why=label)

    def test_ac9_long_lived_file_in_acceptance_dir_is_refused_with_hint(self):
        """Файл `acceptance_tests/test_ac1_long.py` со строкой
        `Группа: долгоживущий` в ветке документов задачи target `artel`
        отклоняет выход; отказ называет файл и подсказывает каталог
        `tests/` (не хвост слова `acceptance_tests/`).

        Ловит мутацию: временная оговорка задачи 1 не снята — долгоживущий
        файл в каталоге приёмочных тестов проходит статические проверки и
        переход уходит в `in_dev`.
        """
        self.artifact_commit(
            {"acceptance_tests/test_ac1_long.py": _sandbox.long_lived_source()},
            "долгоживущий файл в каталоге приёмочных тестов")
        text = self.assert_refused("test_ac1_long.py",
                                   why="долгоживущий файл в планке")
        self.assertRegex(text, TESTS_DIR,
                         "отказ не подсказывает перенести файл в tests/")


if __name__ == "__main__":
    unittest.main()
