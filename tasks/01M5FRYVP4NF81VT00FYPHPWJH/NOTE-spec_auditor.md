# Записка spec_auditor — 01M5FRYVP4NF81VT00FYPHPWJH

## Выяснено
- Адреса SPEC сверены: acceptance.py:37/:709/:725/:3170, advance_gates/acceptance.py:213, fsm.py:1266, tests_writing.py:623, auto.py:313, outcome_integrity.py:65-66/:556/:564, two_sided.py:433/:452, refusal_classes.py:92, doctor/orphans.py:82/:106/:118, liveness.py:27-41 — совпадают.
- G3а-2б-1 (8b47a1f5) уже в базе ветки — порядок «после G3а-2б-1» выполнен, merge_after не нужен.
- Все прогоны компонента по отчёту идут через `_report_argv` (вызовы `_report_run`: acceptance.py:1595/1761/1889/2243/2658, outcome_integrity.py:316, two_sided.py:359). Ключ доказательства гейта исходов на мерже — тот же `_report_suite_result_key` (outcome_integrity.py:399-412), т.е. смена ключа обесценит старые «доказан».
- pytest 9.1.1 `consider_preparse` делает `parg.strip()` → `-p`, ` rerunfailures` и элемент `-p rerunfailures` (с пробелом) грузят плагин; буквальное правило требования 3 их не ловит. В `select`/`report_args` (стоят ПОСЛЕ `-p no:`) это реальный обход. `env.PYTEST_PLUGINS=flaky.flaky_pytest_plugin` не блокируется `-p no:flaky` (блок по имени точки входа `flaky`/`pytest_flaky`).
- AC-4 «та же запись под test_profile отказа не получает» невыполнимо для `select`/`report_args`: их нет в PROFILE_FIELDS (targets.py:45-61) → `_check_profile` откажет «неизвестное подполе» (targets.py:356-360); `env` у test_profile — только при runner: pytest-own (targets.py:370-377).
- Модульный импорт `tests_writing` в fsm.py даст цикл: advance_gates/acceptance.py:17-18 импортирует `fsm` на уровне модуля, tests_writing.py:15 — `.acceptance`; вход через `import orchestrator.advance_gates.acceptance` упадёт ImportError. Нужен ленивый импорт (fsm.py так делает много где).
- `_TOKEN_SPLIT_RE = [\s`,;()«»]+` (mandate.py:392): запятая/скобки — разделители, «иной знак сразу за путём» в AC-10 неоднозначен.
- orphans.py:38 зовёт `_project_clones()` локально, а фасадный `doctor._project_clones` подменяют тесты — точка подмены в SPEC не названа.

## Не сработало
- `cd ... ; sed` в Bash требует подтверждения — читать абсолютными путями/Read.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (8 пунктов), guard — ок.

## Чего не хватило
- Точки подмены `_project_clones` (фасад vs модуль) в ТЗ/SPEC; поведение `-p` pytest пришлось смотреть в исходнике _pytest/config.
