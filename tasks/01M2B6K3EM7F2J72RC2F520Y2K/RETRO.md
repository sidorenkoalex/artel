---
operator: Alexander Sidorenko
model: unknown
artel_sha: 27ddceb310f67a73fc0ab3de0ceec87865a28663
---

# RETRO: 01M2B6K3EM7F2J72RC2F520Y2K — Признак роли в окружении и conftest вместо хука роли

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: Признак роли в окружении и conftest вместо хука роли

Стоимость итого: $27.73
  analyst: $2.27, 3945838 токенов
  test_author: $9.16, 20319764 токенов
  developer: $13.32, 30858495 токенов
  reviewer: $3.00, 4431186 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
планка: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M2B6K3EM7F2J72RC2F520Y2K/tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests, cwd: /Users/al.sidorenko/projects/artel/.artel/worktrees/01M2B6K3EM7F2J72RC2F520Y2K
           [ 92%]
tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/test_ac7_bash_guard_tests_adapted.py s [ 96%]
                                                                         [ 96%]
tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/test_ac8_plan_names_role_home_not_rewritten.py F [100%]

=================================== FAILURES ===================================
_ PlanNamesRoleHomeNotRewrittenTest.test_ac8_plan_influence_section_names_role_home_not_rewritten _

self = <test_ac8_plan_names_role_home_not_rewritten.PlanNamesRoleHomeNotRewrittenTest testMethod=test_ac8_plan_influence_section_names_role_home_not_rewritten>

    def test_ac8_plan_influence_section_names_role_home_not_rewritten(self):
        """`PLAN.md` несёт раздел «Влияние на систему» и в нём — факт о
        том, что развёрнутый `.artel/home/.claude` не переписывается
        автоматически, а расхождение с референсом ловит `doctor
        role-home-reference` (переразворачивает его Оператор вручную).
    
        Ловит мутацию: раздел «Влияние на систему» есть, но пуст по
        существу (общие слова без факта про `.claude` и `doctor
        role-home-reference`) — либо раздел называется иначе и не
        совпадает с требуемым заголовком буквально.
        """
>       self.assertTrue(PLAN.is_file(), f"{PLAN} должен существовать")
E       AssertionError: False is not true : /Users/al.sidorenko/projects/artel/.artel/worktrees/01M2B6K3EM7F2J72RC2F520Y2K/tasks/01M2B6K3EM7F2J72RC2F520Y2K/PLAN.md должен существовать

tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/test_ac8_plan_names_role_home_not_rewritten.py:31: AssertionError
=========================== short test summary info ============================
FAILED tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/test_ac8_plan_names_role_home_not_rewritten.py::PlanNamesRoleHomeNotRewrittenTest::test_ac8_plan_influence_section_names_role_home_not_rewritten
=================== 1 failed, 23 passed, 1 skipped in 2.51s ====================


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
