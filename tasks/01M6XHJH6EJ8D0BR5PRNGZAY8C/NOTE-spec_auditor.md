# Записка spec_auditor 01M6XHJH6EJ8D0BR5PRNGZAY8C (визит 2, SPEC 0b13be6c)

## Выяснено
- Места SPEC сверены повторно: guard.py:4425/4507/1400/1450/1977, test_lint.py:10/190, targets.py:93/1244, project_profile.py:66; вызывающие совпадают.
- Канал перечня heavy не задан: guard.long_lived_errors_from_files получает только (label, текст) файлов, корня/загрузчика нет; AC-7 сигнатура без источника sandbox-текстов.
- Цепочки подклассов межфайловые: MergeOutcomeSandbox (merge_outcome_sandbox.py:61) ← OutcomeGateSandbox; Components*/Prior*/TwoSided/Replacement/Strict — дальше. AC-2 heavy_sandbox_names не требует межфайловой цепочки.
- Вызовы tests_writing:518, preflight:198, amend:293 — по файлам ПЛАНКИ (группа «планка»), до правил размера не доходят; amend:293/317 — только при правиле планки не по умолчанию (_by_rule). AC-6 «4 пути» = 643/725/725/213.
- amend «из планки» :1097 передаёт lint_base = голова кодовой ветки до правки (не tests_locked_sha).

- Идиома `_sandbox(<Песочница>)` (12 файлов) и make_project_repo/isolate_pult_db обходят small; `-m orchestrator.artel` обходит medium.
- Закрытые _pytest* вне guard не зовёт никто — перенос тесты не ломает.

## Где остановился
SPEC-AUDIT.md сдан: verdict concerns (V1 канал heavy в guard, V2 межфайловые цепочки, V3 обходы, V4 пути AC-6, V5 несколько меток), status ready, guard ок.

## Не сработало
- Составные команды с `W=…;` отклоняются — по одной команде, относительные пути.

## Чего не хватило
- Где guard должен брать tests/sandbox.py — в SPEC нет.
