---
operator: Alexander Sidorenko
model: unknown
artel_sha: 0eaac9302e8f8158475cda0ee386cc2ca2208fcb
---

# RETRO: 01M1RDCEF0JZ4AVQRE43JFH8TN — объявленный стек пульта, часть 3 — окружение роли из манифеста, снятие временного хука

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: объявленный стек пульта, часть 3 — окружение роли из манифеста, снятие временного хука

Стоимость итого: $40.86
  analyst: $2.81, 4772815 токенов
  test_author: $8.05, 16461587 токенов
  developer: $16.63, 37631979 токенов
  reviewer: $13.37, 23064741 токенов

Ревью: 2 итераций; приёмка: 0 отказ(ов)

Эскалации: 3 (последняя): приёмочные тесты красные после подтяжки main (слияние сохранено, откат не выполняется):
8, in test_ac4_vars_outside_the_allowlist_do_not_cross_into_role_env
    self.assertNotIn(name, env,
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^
                     f"{name} не входит в белый список, но попал в окружение роли")
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'SOME_RANDOM_VAR' unexpectedly found in {'PATH': '/usr/bin:/bin', 'SOME_RANDOM_VAR': 'нежелательное', 'AWS_SECRET_ACCESS_KEY': 'утечёт-если-скопируют-всё', 'NVM_DIR': '/home/operator/.nvm', 'OPERATOR_SHELL_HISTFILE': '/home/operator/.zsh_history', 'LANG': 'ru_RU.UTF-8', 'LC_ALL': 'ru_RU.UTF-8', 'TMPDIR': '/tmp/operator-tmp', 'TERM': 'xterm-256color', 'HOME': '/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmp7i91hygg/.artel/home', 'CLAUDE_CONFIG_DIR': '/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/tmp7i91hygg/.artel/home/.claude', 'CLAUDE_CODE_OAUTH_TOKEN': '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'} : SOME_RANDOM_VAR не входит в белый список, но попал в окружение роли

======================================================================
FAIL: test_ac6_missing_declared_tool_raises_instead_of_building_env (test_ac6_ac7_ac8_missing_tool_skips_step.RoleEnvRaisesOnMissingToolTest.test_ac6_missing_declared_tool_raises_instead_of_building_env)
`role_env` поднимает исключение, если `which` не находит один
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/folders/4_/y_4xfkg56gd1d_zvk99ntvx00000gq/T/artel-acceptance-01M1RDCEF0JZ4AVQRE43JFH8TN-8od91pd8/acceptance_tests/test_ac6_ac7_ac8_missing_tool_skips_step.py", line 87, in test_ac6_missing_declared_tool_raises_instead_of_building_env
    with self.assertRaises(OSError) as ctx:
         ~~~~~~~~~~~~~~~~~^^^^^^^^^
AssertionError: OSError not raised

----------------------------------------------------------------------
Ran 19 tests in 0.178s

FAILED (failures=5, errors=9)


Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
