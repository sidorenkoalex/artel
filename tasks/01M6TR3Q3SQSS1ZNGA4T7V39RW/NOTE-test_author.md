# Записка test_author — 01M6TR3Q3SQSS1ZNGA4T7V39RW

## Выяснено
- Прошлый запуск шага не оставил ни одного файла планки (отказ трассируемости по всем AC-1…AC-26).
- Bash роли: работают git и python3; `ls`/`cat` недоступны — обход каталогов через python3 -c.
- Замысел: долгоживущий файл tests/test_01m6tr3q3sqss1znga4t7v39rw_role_requests.py — копия пульта
  (orchestrator/, scripts/) в корне RealGitSandbox (как tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py),
  подменённый docker (pid/ppid/psid каждого вызова), драйвер в копии зовёт runner.run_agent_once с
  подменой spawn_agent/role_env/role_cwd; процесс-«агент» исполняет список действий (команды artel.py копии,
  подложить запрос, ждать итог). Разовый файл планки — AC-6 (набор _ROLE_ALLOWED_COMMANDS через ast против
  DIFF_BASE), AC-20/AC-24 (вывод/действие против кода базы в той же песочнице).
- Каталог suite-run = config.LOGS/suite-run → в копии и в процессе теста один и тот же.
- Учёт шага начинается записью agent_log.FRICTION_JOURNAL_ACTION ("agent run friction").

## Не сработало

## Где остановился
- Долгоживущий файл написан (все AC кроме 6-набор/20/24); зелёные с рождения AC-6/7/18/19/21 прошли
  (песочница, подменённый docker и compose-проект рабочие); драйвер run_agent_once в копии доходит
  до DRIVER-RESULT ok, «агент» в роли исполняет команды — краснота AC-1/2/5/26 по верной причине.
- Разовый файл acceptance_tests/test_unchanged_forms.py написан (AC-6 набор, AC-20, AC-24), гоняю.

## Чего не хватило
