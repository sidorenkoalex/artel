"""`doctor --fix` заводит клоны проектов раньше досылки закрытых ссылок,
и обе починки идут раньше проверок.

Группа: разовый

Почему разовый: критерий AC-8 называет закрытые функции фасада doctor
(`_fix_project_clones`, `_fix_unsent_closed_refs`), а долгоживущий файл
`tests/` подменять закрытые имена `orchestrator` не вправе
(skills/test-authoring.md); постоянный тест порядка в `tests/` пишет
разработчик (требование 5 SPEC), AC-9 сторожит его заявку.

Песочница — `tests.sandbox.SchemaTmpRootTest` (пути `config` во временном
каталоге, схема БД). Обе починки и `all_checks` подменены записью вызова в
общий журнал порядка; прочие починки ветки `--fix` — пустышками, чтобы
сценарий не зависел от их окружения.

Красен до реализации: `cmd_doctor` зовёт `_fix_unsent_closed_refs` в
начале ветки `--fix`, а `_fix_project_clones` — последней починкой, после
неё. Провалидирован временным стабом (перенос `_fix_project_clones` перед
`_fix_unsent_closed_refs`; удалён, не закоммичен).
"""
import unittest
from contextlib import ExitStack
from unittest import mock

from _plank import git  # noqa: F401  (кладёт корень рабочей копии в sys.path)

from orchestrator import doctor
from tests.sandbox import SchemaTmpRootTest, capture

OTHER_FIXES = ("_fix_ignored_artifact_files", "_fix_dead_lease_groups",
               "_fix_hung_test_runs", "fix_models_local", "_fix_git_hooks")


class DoctorFixOrderTest(SchemaTmpRootTest):

    def test_ac8_clones_before_closed_refs_before_checks(self):
        """`_fix_project_clones` вызывается раньше `_fix_unsent_closed_refs`, обе — раньше `all_checks`.

        Сценарий: `cmd_doctor(fix=True)` с подменёнными двумя починками и
        `all_checks`, каждая подмена дописывает своё имя в журнал порядка.
        В журнале каждое имя встречается, и позиция первого вызова
        `_fix_project_clones` меньше позиции `_fix_unsent_closed_refs`,
        а та меньше позиции `all_checks`.

        Ловит мутацию: порядок в ветке `--fix` прежний — досылка закрытых
        ссылок раньше заведения клонов (свежий клон без ссылок досылка не
        видит); заведение клонов перенесено после `all_checks` — проверки
        не видят результата.
        """
        order = []

        def recorder(name, result=None):
            def record(*_args, **_kwargs):
                order.append(name)
                return result
            return record

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                doctor, "_fix_project_clones", recorder("clones")))
            stack.enter_context(mock.patch.object(
                doctor, "_fix_unsent_closed_refs", recorder("closed_refs")))
            stack.enter_context(mock.patch.object(
                doctor, "all_checks", recorder("checks", [])))
            for name in OTHER_FIXES:
                if hasattr(doctor, name):
                    stack.enter_context(mock.patch.object(
                        doctor, name, recorder(name)))
            capture(lambda: doctor.cmd_doctor(fix=True))

        for name in ("clones", "closed_refs", "checks"):
            self.assertIn(name, order, f"не вызвана: {name}; порядок {order}")
        self.assertLess(order.index("clones"), order.index("closed_refs"),
                        f"заведение клонов не раньше досылки: {order}")
        self.assertLess(order.index("closed_refs"), order.index("checks"),
                        f"досылка не раньше all_checks: {order}")


if __name__ == "__main__":
    unittest.main()
