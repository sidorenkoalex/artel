# Записка test_author (G1а-2)

## Выяснено
- `doctor.subprocess`/`doctor.shutil` — сами модули stdlib (фасад
  orchestrator/doctor/__init__.py), подмена `doctor.subprocess.run` глобальна;
  TmpRootTest уже ставит SpyRun(passthrough) на subprocess.run — обёртка
  теста делегирует ему всё, кроме учебных инструментов и `gh`.
- `shutil.which` в песочнице глобально заглушен (`_stub_which`, sandbox.py:134)
  только для имён gh/claude — учебные имена инструментов взяты иными (`zt…`).
- Ключ рабочего дерева сегодня `suite_result_key(tree, command)` без корня —
  игнорируемый файл блокировки ему не виден; разработчику придётся передать
  корень по цепочке вызова. Поэтому AC-13/AC-15 планка проверяет через
  `acceptance.full_suite` (повторный ли итог при подменённом `run_full_suite`,
  имена `gate-<ключ>.json`/`base-<ключ>.json` в `suite_results_dir()`), а не
  через сигнатуру.
- `_task_own_profile` у pult-pytest даёт None — для AC-12 «test_profile» взята
  запись pytest-own с test_profile (как отметил spec_auditor, V4).
- AC-15 «до правки» сверяется с `orchestrator/acceptance.py` ревизии
  `_pult.DIFF_BASE`, загруженным отдельным модулем пакета orchestrator
  (`_keys.acceptance_at_base`).
- Учебные CI-файлы и каталоги `workdir` лежат в клоне только на диске (не
  закоммичены): долгоживущему файлу git через subprocess нельзя.

## Не сработало
- Heredoc с `{…"` в Bash отклоняется — стаб вносил инструментом Edit.

## Где остановился
- Готово, предпроверка `preflight` пройдена целиком.
- tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py (долгоживущий,
  AC-1..AC-11 + AC-15 doctor): до реализации 12 красных (TargetsError из
  full_suite_limit), AC-15 зелёный с рождения; на стабе 12/12 зелёные,
  мутации «префикс строки», «contract в объединении» ловятся.
- acceptance_tests/ (разовый): test_tools_key.py (AC-12, AC-13 — красные),
  test_base_and_unchanged_key.py (AC-14, AC-15 — зелёные с рождения),
  _keys.py — общая песочница. На стабе 4/4 зелёные; мутации «tools в ключе
  базы» (AC-14) и «новый элемент при пустых tools» (AC-15) ловятся.
- Все стабы откачены `git checkout --`; в рабочей копии — только новый файл
  tests/.
- Карта docs/codebase-map.md не регенерирована: правка вне tests/ у
  test_author откатывается пультом — регенерация за разработчиком.

## Чего не хватило
- Формы `Profile.tools` SPEC не задаёт — тест сравнивает `dict(tools)`.
