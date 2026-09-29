"""AC-10, AC-11, AC-12: прогон долгоживущих файлов в изолированной
выгрузке на выходе из `tests_writing`.

Песочница — `_sandbox.ExportSandbox` (настоящий git пульта, bare
`origin`, worktree кодовой ветки; база ветки несёт `tasks/`). Фикстурный
долгоживущий файл `_sandbox.EXPORT_FIXTURE` проходит проверку по тексту, а
его исход задают флаги каталога управления вне репозиториев: «окольный
путь» — метод требует `.git` рядом с `tests/` (есть в рабочей копии, нет в
выгрузке), «сбор» — модуль падает при импорте вне рабочей копии,
«пропуск» — `skipTest` через помощника `getattr`, «красный» — `fail` в
обоих прогонах, «наблюдение» — метод пишет рабочий каталог, `HOME`,
наличие `.git`/`tasks/` и ответ `git rev-parse` в файл каталога
управления.

Группа: разовый
Красен до реализации: выхода из `tests_writing` с прогоном в выгрузке нет — окольный метод, сбой сбора вне рабочей копии и пропуск через помощника проходят переход в `in_dev`, наблюдений из выгрузки нет; честный файл на `tests/sandbox.py` нынешний guard отклоняет по признакам «git-модуль»/`tasks/`. Метод «красный в обоих прогонах» зелёный с рождения: нынешний выход красный тест пропускает.

Валидация стабом (временная реализация признаков в `scripts/guard.py`,
прогона в выгрузке `git archive` + junit-отчёт в `orchestrator/acceptance.py`
и трёх точек встраивания; откачена): все методы файла зелёные.

Почему разовый: сценарий строит ветку документов через `artifact_branch`,
зовёт git через `subprocess` и читает `tasks/` — признаки, которые
нынешний (до этой задачи) guard запрещает долгоживущему файлу;
долгоживущие тесты требований 9-12 пишет разработчик (требование 15 SPEC).
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (EXPORT_HINT, EXPORT_METHOD, REPO_ROOT,  # noqa: E402
                      ExportSandbox, honest_fixture, is_within, real)


class TestsWritingExportTest(ExportSandbox):

    def setUp(self):
        super().setUp()
        self.wt_commit({self.own: self.export_fixture()})

    def assert_refused(self, text: str, why: str) -> None:
        self.assertEqual(self.state(), "tests_writing",
                         f"{why}: выход обязан быть отклонён: {text}")
        self.assertIn(self.own_name(), text, f"{why}: отказ не называет файл")

    def test_ac10_export_is_isolated_from_real_repository(self):
        """Метод, наблюдающий среду прогона и требующий `.git` рядом с
        `tests/`, — выход отклонён; в выгрузке (запись без `.git`) нет и
        `tasks/`, корень выгрузки, рабочий каталог и `HOME` — вне
        репозитория пульта, рабочей копии и настоящего репозитория, `HOME`
        не унаследован, `git rev-parse` ни из корня выгрузки, ни из рабочего
        каталога не находит ни один из этих репозиториев; в рабочей копии
        метод зелёный (запись с `.git`).

        Ловит мутацию: выгрузка собрана копией рабочего каталога (`.git`,
        `tasks/` на месте) или pytest запущен с `cwd` рабочей копии и
        прежним `HOME` без `GIT_CEILING_DIRECTORIES` — запись выгрузки
        несёт `.git`/`tasks/`, либо `cwd`/`HOME`/`toplevel` указывают в
        репозиторий.
        """
        self.arm("observe", "roundabout")
        text = self.exit_tests_writing()
        self.assert_refused(text, "окольный путь")
        records = self.observations()
        in_copy = [r for r in records if r["dotgit"]]
        exported = [r for r in records if not r["dotgit"]]
        self.assertTrue(in_copy, f"нет прогона в рабочей копии: {records!r}")
        self.assertTrue(exported, f"нет прогона в выгрузке: {records!r}")
        repos = (self.root, self.wt, REPO_ROOT)
        real_home = real(os.environ.get("HOME", ""))
        for record in exported:
            with self.subTest(record=record):
                self.assertFalse(record["tasks"], "выгрузка несёт tasks/")
                for key in ("here", "cwd", "home"):
                    for repo in repos:
                        self.assertFalse(is_within(record[key], repo),
                                         f"{key} внутри {repo}")
                self.assertNotEqual(real(record["home"]), real_home,
                                    "HOME унаследован от пульта")
                for key in ("top_here", "top_cwd"):
                    code, top = record[key]
                    if code == 0:
                        for repo in repos:
                            self.assertNotEqual(real(top), real(str(repo)),
                                                f"git из {key} нашёл {repo}")

    def test_ac11_green_in_copy_red_in_export_refused(self):
        """Метод зелёный в рабочей копии и красный в выгрузке — выход
        отклонён, отказ называет файл, метод и подсказку «тест привязан к
        настоящему репозиторию — строй копию через tests/sandbox.py».

        Ловит мутацию: прогон в выгрузке не встроен в выход (или его исход
        не сравнивается с рабочей копией) — задача уходит в `in_dev`.
        """
        self.arm("roundabout")
        text = self.exit_tests_writing()
        self.assert_refused(text, "окольный путь")
        self.assertIn(EXPORT_METHOD, text)
        self.assertIn(EXPORT_HINT, text)

    def test_ac11_collect_error_in_export_refused(self):
        """Модуль собирается в рабочей копии и падает при сборе в выгрузке
        — выход отклонён с именем файла.

        Ловит мутацию: отчёт выгрузки разбирается только по методам, ошибка
        сбора (ни одного метода в отчёте) засчитана проходом.
        """
        self.arm("collect")
        text = self.exit_tests_writing()
        self.assert_refused(text, "ошибка сбора в выгрузке")

    def test_ac11_red_in_both_runs_is_not_refused(self):
        """Метод красный и в рабочей копии, и в выгрузке — выход проходит
        в `in_dev` (красный тест до кода — норма).

        Ловит мутацию: отказ по любому не зелёному исходу в выгрузке без
        сравнения с рабочей копией — красный до реализации тест держит
        задачу в `tests_writing`.
        """
        self.arm("red")
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", text)

    def test_ac12_skip_through_helper_refused_by_report(self):
        """Метод пропущен через помощника (`getattr(case, "skip" + "Test")`,
        проверке по тексту не виден) — выход отклонён по отчёту прогона с
        именем файла и метода и словом «пропуск».

        Ловит мутацию: отчёт разбирается как «не упал — значит зелёный»,
        пропуск засчитан проходом — задача уходит в `in_dev`.
        """
        self.arm("skip")
        text = self.exit_tests_writing()
        self.assert_refused(text, "пропуск через помощника")
        self.assertIn(EXPORT_METHOD, text)
        self.assertIn("пропуск", text.lower())


class TestsWritingHonestFileTest(ExportSandbox):

    COPY_CODE = True

    def test_ac11_honest_sandbox_file_passes(self):
        """Честный долгоживущий файл на `tests/sandbox.py` (ветка документов
        во временной копии `RealGitSandbox`) при чистом фикстурном файле —
        выход проходит в `in_dev`.

        Ловит мутацию: выгрузка не несёт `tests/sandbox.py`/`orchestrator/`
        (архивирован один файл задачи) или pytest в выгрузке не находит
        корень выгрузки — честный файл красен только там, и переход
        отклонён.
        """
        self.wt_commit({self.own: self.export_fixture(),
                        f"tests/test_{self.TASK.lower()}_honest.py":
                            honest_fixture()})
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", text)


if __name__ == "__main__":
    unittest.main()
