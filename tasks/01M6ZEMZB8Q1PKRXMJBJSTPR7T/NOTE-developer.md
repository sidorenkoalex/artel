# Записка developer — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Реализация готова (WIP-чекпоинт 196c5e8f8): config.py, acceptance.py (блок «шаблон байткода»,
  _place_env — contextmanager, наполняет при run_dir; _own_env наполняет сам), tests/sandbox.py.
  Карта перегенерирована в этом шаге.
- Зелёные после подтяжки main: 3 долгоживущих файла задачи, залоченный pycache, test_acceptance_pycache,
  doctor_duration, full_suite_profile_timeout, test_acceptance, test_acceptance_tests_flow — 208 passed.
- Красный: tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py:65 (`cache.iterdir() == []` у
  полного прогона) — прямое противоречие требованию 7. PLAN status: escalate, вопрос 1 — мандат на правку строки 65.
- test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged ac7, подтест two_sided: «git не ответил на голову
  ветки» (gitcmd.branch_head_sha) в окружении роли — не код задачи.

## Не сработало
- В окружении роли нет cat/ls; `python3 <файл каталога документов>` требует подтверждения.
  Отладку делать через pytest по tests/<файл>.

## Где остановился
- Эскалация сдана. После ANSWER: правка строки 65 (если мандат), прогон файла, PLAN status: ready.

## Чего не хватило
- SPEC требование 10 не перечислило timeout_integrations.py:65 среди тестов, задетых механикой.
