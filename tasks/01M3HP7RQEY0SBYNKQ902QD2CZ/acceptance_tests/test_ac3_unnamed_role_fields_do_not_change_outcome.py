"""AC-3: тест `tests/`, чей предмет не карта ролей, даёт ТОТ ЖЕ исход при
другом допустимом значении полей `provider:`, `model_tier:`, `skills:`,
`token_slot:` у ролей, которых он не называет.

Перечень таких тестов — читатели боевой карты (`_util.map_reader_tests`)
за вычетом тех, кого PLAN.md назвал тестами самой карты
(`_util.ac3_targets`). Классификация PLAN.md только СУЖАЕТ перечень:
пока PLAN.md нет, планка прогоняет всех читателей, то есть строже, а не
мягче.

«Роли, которых тест не называет» считаются по тексту файла: роль, чьё имя
в файле не встречается, сценарием не выбрана, и её поля исход менять не
имеют права. Файлы сгруппированы по набору названных ролей — у каждой
группы своя карта и своя копия дерева кода, и все группы прогоняются
одновременно: восемь последовательных прогонов не уложились бы в потолок
прогона планки (`config.ACCEPTANCE_TIMEOUT_SEC`).

Значения подменяются ДОПУСТИМЫЕ, а не поломанные: провайдер из реестра
`orchestrator/providers`, ярус из перечня `models.TIERS`, скил и слот
токена, уже названные самой картой. Карта остаётся валидной — краснота
под такой подменой и есть предмет задачи.

«Тот же исход», а не «зелено»: исход на подменённой карте сравнивается с
исходом тех же файлов на НАСТОЯЩЕЙ карте репозитория
(`_util.baseline_failures`).

Красен до реализации: сегодня карта исполнителей приезжает в песочницу
`tests/` из боевого файла, и чужое значение `provider:`/`model_tier:`
ломает разрешение цепочки «роль -> ярус -> модель -> провайдер» у файлов,
которые про провайдеры ролей ничего не утверждают (раздел «Контекст»
SPEC, инцидент 27.09).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class UnnamedRoleFieldsTest(unittest.TestCase):
    """Подмена полей у ролей, которых файл не называет."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac3_fields_of_unnamed_roles_do_not_change_the_outcome(self):
        """Каждый тест `tests/`, чей предмет не карта ролей, прогоняется на
        карте, где у всех НЕ названных им ролей стоят другие допустимые
        значения четырёх полей, и даёт тот же исход, что на настоящей
        карте.

        Ловит мутацию: фикстура песочницы выведена из боевого файла
        снятием одного поля (текст `roles.yaml` без строк `provider:`) —
        `provider:` закрыт, а `model_tier:`, `skills:` и `token_slot:`
        по-прежнему приезжают из боевой карты, и перевод чужой роли на
        другой ярус снова красит файлы, которые про ярусы не утверждают
        ничего (ровно так 27.09 упал `tests/test_stack_optional_tools.py`).
        """
        targets = [rel for rel in _util.ac3_targets()
                   if (_util.REPO_ROOT / rel).is_file()]
        self.assertTrue(
            targets,
            "среди читателей боевой карты не осталось ни одного файла, чей "
            "предмет не карта ролей, — проверять нечего")
        self.assertIn(
            _util.ANALYST_TEST, targets,
            f"{_util.ANALYST_TEST} выбыл из перечня тестов, чей предмет не "
            f"карта ролей, — AC-5 требует от него прохождения на карте с "
            f"чужим `provider:`, то есть предмет у него не карта")

        base_failures, base_broken, base_report = \
            _util.baseline_failures(targets)
        self.assertEqual(
            base_broken, [],
            f"прогон перечня на НАСТОЯЩЕЙ карте сломался целиком — сравнивать "
            f"исходы не с чем\n{base_report}")
        text = _util.real_roles_text()
        all_roles = set(_util.role_entries(text))

        groups = {}
        for rel in targets:
            named = frozenset(_util.roles_named_in(rel, text))
            groups.setdefault(named, []).append(rel)

        jobs = []
        for i, (named, files) in enumerate(sorted(
                groups.items(), key=lambda item: sorted(item[1]))):
            unnamed = sorted(all_roles - set(named))
            if not unnamed:
                continue
            mutated = _util.roles_text_with(
                text, _util.other_field_values(text, unnamed))
            self.assertNotEqual(
                mutated, text,
                f"подмена полей у ролей {unnamed} не изменила текста карты — "
                f"сценарий AC-3 не разыгран")
            code = _util.repo_copy(self.tdir, mutated, name=f"group-{i}")
            jobs.append((code, files))

        self.assertTrue(
            jobs,
            "у каждого файла перечня названы все роли карты — «роли, "
            "которых тест не называет» в сценарии AC-3 не нашлось")

        try:
            results = _util.run_pytest_many(jobs, timeout=110)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover
            self.fail(f"прогоны на подменённых картах не уложились в "
                      f"отведённое время: {exc}")

        self.assertEqual(
            _util.many_broken(results), [],
            f"прогон на подменённой карте сломался целиком, ни одного "
            f"названного теста\n{_util.many_report(results)}")
        self.assertEqual(
            _util.many_failures(results), base_failures,
            f"исход изменился от подмены полей у ролей, которых тест не "
            f"называет\nна настоящей карте:\n{base_report}\n"
            f"на подменённых картах:\n{_util.many_report(results)}")


if __name__ == "__main__":
    unittest.main()
