# Записка test_author — 01M5FRYVP4NF81VT00FYPHPWJH

## Выяснено
- Прошлая попытка не оставила ни одного файла планки (отказ трассируемости по всем 14 AC). Написано заново.
- Раскладка. Планка (группа «разовый»: критерии называют закрытые имена, а guard запрещает их долгоживущим файлам):
  test_report_argv_rerun_ban.py (AC-1..3), test_spec_gate_detail.py (AC-5),
  test_gate_owner_marker.py (AC-6..8), test_mandate_coverage_bounds.py (AC-9, AC-10).
- Долгоживущие: tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py (AC-4, AC-13, AC-14),
  tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py (AC-11, AC-12).
- AC-14 («возвращает отказ … без исключения наружу»): у targets.check единственный канал отказа — raise TargetsError. Тест ждёт TargetsError с текстом «PYTEST_ADDOPTS не разбирается»; ValueError, вышедший наружу, — провал (к1 аудитора).
- AC-6: подменяется gitcmd.in_repo; на `worktree add` тест читает маркер в родителе пути выписки. AC-8: настоящий git в клоне во временном каталоге, вызовы git видны через подмену subprocess.Popen.
- AC-9/AC-10: путь через mandate.matrix_refusals, подменён только mandate._task_decision.
- Стаб корректной реализации в orchestrator/ (9 файлов) дал полную зелень: планка 10/10, долгоживущие 6/6. Мутации «prune всегда» и «флаги в хвосте argv» пойманы. Стаб откатан (git checkout -- orchestrator/).
- До реализации: планка — 22 failed / 6 passed (AC-9 зелёный с рождения), долгоживущие красные по верной причине. Предпроверка preflight: все пункты пройдены.

## Не сработало
- `ls` в Bash не находится; листинг — через python3 os.walk.
- URL `https://example.invalid` в tests/ отклонён инвариантом 35, заменён на 127.0.0.1.

## Где остановился
- Шаг завершён: планка и долгоживущие файлы готовы, preflight зелёный.
- Карту docs/codebase-map.md не регенерировал: правка вне tests/ test_author недоступна, карту обновит developer.

## Чего не хватило
- Ничего существенного; дольше всего разбирался в составе argv _report_argv (подмножество, `--ignore` выкладки) — проверял пробным запуском.
