"""AC-4: мутации из докстринга метода предела `suite-run` по-прежнему краснят его.

Группа: разовый
Зелёный с рождения: метод сегодня ловит обе мутации докстринга (без обрыва по пределу профиля отчёта «не уложился» нет; с числом config в отчёте `standalone(60)` срабатывает), а копия дерева без мутации даёт зелёный метод — планка держит, что правка задачи этого не потеряла.

Мутации вносятся в `orchestrator/suite_run.py` временной копии рабочей
копии кода (без `.git`, `tasks/`, `.artel/`); метод гоняется вложенным
pytest из копии и копирует пульт для своей песочницы оттуда же
(`CODE_ROOT` теста — родитель импортированного `acceptance`).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _meta import copy_tree, mutate, run_limit_test  # noqa: E402

SUITE_RUN = "orchestrator/suite_run.py"


class DocstringMutationsTest(unittest.TestCase):

    def run_in_copy(self, *mutation):
        holder = Path(tempfile.mkdtemp(prefix="artel-ac4-tree-")).resolve()
        self.addCleanup(shutil.rmtree, holder, True)
        root = copy_tree(holder / "tree")
        if mutation:
            mutate(root, SUITE_RUN, *mutation)
        return run_limit_test("natural", root=root)

    def test_ac4_unmutated_copy_keeps_method_green(self):
        """Копия дерева без мутации — метод предела зелёный.

        Сценарий: та же временная копия, что у мутаций ниже, без правок;
        метод гоняется из неё. Зелёный исход здесь — условие того, что
        краснота под мутацией идёт от мутации, а не от копии.

        Ловит мутацию: метод зависит от файлов вне копируемого дерева
        (`.git` рабочей копии, `tasks/`, `.artel/`) или от абсолютного пути
        рабочей копии — из копии он красен, и краснота под мутациями ничего
        не доказывает.
        """
        run = self.run_in_copy()
        self.assertEqual(run.outcome, "passed", run.context())

    def test_ac4_background_run_using_config_limit_reddens_method(self):
        """Фоновый `suite-run` берёт `config.FULL_SUITE_TIMEOUT_SEC` вместо подполя профиля — метод красен.

        Сценарий: в `_run` копии `limit = project_profile.full_suite_limit(
        target)` заменено на `(config.FULL_SUITE_TIMEOUT_SEC, "config")`;
        метод предела проваливает утверждение (исход `failed`; страховочный
        потолок `--wait` здесь вправе решить исход).

        Ловит мутацию: подмена часов теста переводит часы и обрывает прогон
        при любом пределе, а не только при N профиля (или пробник не
        отпускается при чужом пределе, и утверждения ослаблены) — метод
        зелёный под мутацией.
        """
        run = self.run_in_copy(
            "    limit = project_profile.full_suite_limit(target)\n",
            '    limit = (config.FULL_SUITE_TIMEOUT_SEC, "config")\n')
        self.assertEqual(run.outcome, "failed", run.context())

    def test_ac4_timeout_report_printing_config_value_reddens_method(self):
        """Отчёт о таймауте печатает значение config, а не N, — метод красен.

        Сценарий: в `render` копии в строке «прогон не уложился в предел …»
        число предела заменено на `config.FULL_SUITE_TIMEOUT_SEC` (60 копии);
        обрыв по-прежнему по N. Метод предела проваливает утверждение
        (исход `failed`).

        Ловит мутацию: утверждения «N в строке» или «нет отдельно стоящего
        COPY_LIMIT» сняты или ослаблены — метод зелёный под мутацией.
        """
        run = self.run_in_copy(
            'f"прогон не уложился в предел {seconds} с "',
            'f"прогон не уложился в предел {config.FULL_SUITE_TIMEOUT_SEC} с "')
        self.assertEqual(run.outcome, "failed", run.context())


if __name__ == "__main__":
    unittest.main()
