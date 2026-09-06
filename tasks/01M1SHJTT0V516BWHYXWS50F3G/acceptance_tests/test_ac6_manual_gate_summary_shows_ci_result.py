"""AC-6: если задача приехала на ручной гейт приёмки, сводка гейта
(`orchestrator/acceptance.py::summary`) показывает критерий с пометкой
`ci` вместе с результатом проверки CI — так же явно, как сегодня
показываются manual-критерии.

Сигнатура `summary()` не названа SPEC буквально — тест зовёт функцию с
именем ветки КОДА задачи вторым (keyword) аргументом `branch=`,
следующим тому же соглашению, что уже несёт весь остальной модуль
(`ci.branch_status(branch)`, `ci.verifying_status(branch)`,
`materialize_from_branch(task_id, branch, code_dir)`) — по сути та же
информация, которая нужна условию «а» автогейта (AC-4/AC-5) для того
же вопроса «зелёный ли CI кодовой ветки».

Красен до реализации: сегодняшняя `summary(tdir)` принимает единственный
позиционный параметр и вообще не знает о пометке `ci` (список markers
фильтруется только на `manual`/`skip`) — вызов с `branch=` упадёт
`TypeError` («unexpected keyword argument»), не просто вернёт сводку без
CI-строки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateCiMarkerSandbox, ci_only_planka  # noqa: E402

from orchestrator import acceptance  # noqa: E402


class Ac6ManualGateSummaryShowsCiResultTest(AutogateCiMarkerSandbox):

    def _write_disk_planka(self, content: str) -> Path:
        """`summary()` читает ДИСК (не артефактную ветку, в отличие от
        условия «а» автогейта, AC-1 задачи 01M1NBWWPJMHKJMYXRDCM0W0C5) —
        планка кладётся прямо в `tasks/<id>/acceptance_tests/` рабочей
        копии песочницы."""
        tdir = self.root / "tasks" / self.TASK
        tests_dir = tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")
        return tdir

    def test_ac6_summary_names_ci_criterion_with_ci_status(self):
        """Планка несёт единственную пометку `# AC-2: ci`, CI кодовой
        ветки красный — сводка гейта называет номер критерия (AC-2) и
        упоминает слово «ci» (та же явность, что и у `manual`-списка
        сегодня: `summary()` перечисляет их номера отдельной строкой).

        Ловит мутацию: `summary()`, оставленная без изменений (видит
        только `manual`/`skip` списки) — критерий `ci` в сводке не
        появится вовсе, тест поймает отсутствие «AC-2» в тексте.
        """
        tdir = self._write_disk_planka(ci_only_planka(2))

        with self.gh_check_runs(conclusion="failure"):
            card = acceptance.summary(tdir, branch=self.branch)

        self.assertIn("AC-2", card)
        self.assertIn("ci", card.lower())


if __name__ == "__main__":
    unittest.main()
