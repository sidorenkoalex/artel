"""AC-18/AC-19: PLAN перечисляет обновлённые ожидания по удалённой
таблице совместимости и несёт приложением unified-дифф к `roles.yaml`,
который применяется на чистом дереве; сам `roles.yaml` веткой не изменён.

Вторая половина AC-18 («полный прогон `tests/` зелёный») тестом планки не
дублируется: полный набор гоняют автогейт (`orchestrator/fsm_autogate.py`
-> `acceptance.run_full_suite`) и CI кодовой ветки — отсюда пометка `ci`
сразу после докстринга, рядом с тестом на проверяемую половину критерия.

PLAN.md читается ТОЛЬКО с артефактной ветки (`_repo.plan_text`): на диске
в среде прогона планки пультом лежит один `acceptance_tests/`.

Красен до реализации: PLAN.md ещё не написан (его создаёт роль developer)
— обоих разделов нет ни в одном источнике.
"""
import re
import unittest

import _repo

# AC-18: ci — «полный прогон tests/ зелёный» подтверждают зелёный CI кодовой
# ветки и прогон полного набора автогейтом; планка не вправе запускать набор
# из набора, поэтому тестом ниже проверена вторая половина критерия —
# перечень обновлённых ожиданий в PLAN.

# Файлы, названные AC-18 как те, чьи ожидания по удалённой таблице
# совместимости обновляются.
NAMED_TESTS = ("tests/test_providers.py", "tests/test_runner_role_model.py",
               "tests/test_runner_model_preflight.py", "tests/test_stack.py",
               "tests/test_doctor.py")
TABLE_MENTIONS = ("MODEL_MIN_CLI_VERSION", "таблиц")

ROLES_FILE = "roles.yaml"
TIERED_ROLES = ("analyst", "test_author", "developer", "reviewer")
_DIFF_BLOCK_RE = re.compile(
    r"```diff\n(diff --git a/" + re.escape(ROLES_FILE)
    + r" b/" + re.escape(ROLES_FILE) + r".*?)\n```", re.DOTALL)


class PlanTest(unittest.TestCase):

    def setUp(self):
        self.plan = _repo.plan_text()
        self.assertIsNotNone(
            self.plan,
            f"PLAN.md задачи {_repo.TASK_ID} ещё нет в артефактной ветке — "
            f"оба раздела пишет роль developer")

    def test_ac18_plan_lists_updated_compatibility_table_expectations(self):
        """PLAN называет удалённую таблицу совместимости и файлы `tests/`,
        чьи ожидания о ней обновлены.

        Ловит мутацию: ожидания в `tests/` поправлены молча — ревьювер и
        Оператор не видят списка того, что изменилось вокруг удалённой
        таблицы, и вынуждены вычитывать его из диффа по всему набору.
        """
        self.assertTrue(
            any(m in self.plan for m in TABLE_MENTIONS),
            f"PLAN не называет удалённую таблицу совместимости "
            f"({', '.join(TABLE_MENTIONS)})")
        named = [t for t in NAMED_TESTS if t in self.plan]
        self.assertTrue(
            named,
            f"PLAN не называет ни одного файла из {', '.join(NAMED_TESTS)}")

    def test_ac19_plan_attaches_an_applicable_roles_yaml_diff(self):
        """PLAN несёт ```diff-блок по `roles.yaml`: `model_tier: strong` у
        четырёх agent-ролей и удаление у них поля `model`; блок проходит
        `git apply --check` на чистом дереве базы интеграции.

        Ловит мутацию: приложение оформлено пересказом («добавить
        model_tier четырём ролям») или диффом с фиктивным заголовком хунка
        — пульт на мерже применить его не сможет, и конвейер встанет с
        `roles.yaml` без ярусов при коде, который читает только ярусы.
        """
        match = _DIFF_BLOCK_RE.search(self.plan)
        self.assertIsNotNone(
            match, f"в PLAN нет ```diff-блока с 'diff --git a/{ROLES_FILE} "
                   f"b/{ROLES_FILE}'")
        diff_text = match.group(1) + "\n"

        added = [ln for ln in diff_text.splitlines()
                 if re.match(r"^\+\s*model_tier:\s*strong\b", ln)]
        removed = [ln for ln in diff_text.splitlines()
                   if re.match(r"^-\s*model:\s", ln)]
        self.assertEqual(len(added), len(TIERED_ROLES),
                         f"строк 'model_tier: strong' в приложении: {added}")
        self.assertEqual(len(removed), len(TIERED_ROLES),
                         f"снятых строк 'model:' в приложении: {removed}")
        for role in TIERED_ROLES:
            with self.subTest(role=role):
                self.assertIn(role, diff_text)

        applies, diagnosis = _repo.applies_to_integration_base(diff_text)
        self.assertTrue(applies, f"git apply --check отказал:\n{diagnosis}")

    def test_ac19_roles_yaml_is_not_changed_by_the_task_branch(self):
        """Дифф ветки задачи (с незакоммиченным) не трогает `roles.yaml`.

        Ловит мутацию: разработчик правит `roles.yaml` прямо в ветке,
        чтобы «шаги не встали», — защищённый путь меняется мимо Оператора,
        и гейт защищённых путей ловит это только на выходе из `in_dev`,
        уже после работы.
        """
        self.assertNotIn(ROLES_FILE, _repo.changed_paths_since_main())


if __name__ == "__main__":
    unittest.main()
