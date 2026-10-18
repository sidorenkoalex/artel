# Записка spec_auditor — 01M58FNWBV25FF26E7AZ9Q9912 (аудит SPEC f65ba288, второй визит)

## Выяснено
- SPEC второй редакции учёл ANSWER-1 (вариант B yamlmini, деление на часть 1). Ссылки на код в основном верны; неточности: `PROFILE_OWN_RUNNER_ONLY` — targets.py:73 (не :71); стр. «77-80» теста — на деле 71-74 (tests/test_acceptance_suite_profile.py).
- `_task_own_profile` (acceptance.py:2380) зовут pull.py:665, plank_run.py:220, amend.py:548/723 и `drop_from_code_copy` (acceptance.py:1298), а его — runner.py:1218 на старте КАЖДОГО шага роли, checkpoint.py:1237, fsm_advance.py:607, amend.py:765. Форма «отказа» требования 9 не задана: raise уронит старт шага, возврат не-None сломает `command=own`.
- doctor/cli.py:94 зовёт `full_suite_limit` без try: после требования 8 запись с двумя компонентами роняет весь `doctor` (cli.py вынесен из зон SPEC, хотя в зонах ТЗ).
- yamlmini: ключ режется по первому `:` (yamlmini.py:146) — имя с `:` из файла не записать, только словарём; повтор ключа молча перезаписывает.

## Где остановился
SPEC-AUDIT.md записан, verdict concerns, guard прогнан.

## Чего не хватило
Карты вызывающих `drop_from_code_copy` — искал grep'ом по orchestrator/.
