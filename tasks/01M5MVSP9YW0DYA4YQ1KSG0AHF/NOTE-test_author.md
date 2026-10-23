# Записка test_author — 01M5MVSP9YW0DYA4YQ1KSG0AHF

## Выяснено
- Планка: AC-2 — разовый acceptance_tests/test_ac2_plan_appendix.py (PLAN через _pult.artifact_text, apply_check, прогон DeterministicTestsLintTest во временной копии с приложением). AC-1, AC-3..AC-8 — долгоживущие файлы tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_{test_lint,exit_gates,amend_lint}.py.
- Песочница на настоящем git — по образцу tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py. Draft MR на входе в in_dev зовёт настоящий gh — подменён github_adapter.ensure_draft_mr.
- Правку планки на --from-branch коммитить в ссылку документов через worktree + update-ref и затем store.record_fixation, иначе amend-tests видит инцидент «ссылка сдвинута мимо пульта». checkpoint.commit_step_artifacts после коммита убирает каталог документов.
- Стаб (test_lint из класса test_invariants, guard.lint_errors_from_files + lint_base, подключение в amend.py с базой лока и поиском ревизии по сумме) — все тесты зелёные; мутации «база = родитель головы» и «метки снимка не приведены» краснят 3 теста AC-6. Стаб удалён, git status чист, кроме трёх новых файлов tests/.
- preflight: все проверки пройдены.

## Не сработало
- Bash: составные команды с cp/пайпами требуют подтверждения — делал одним python3-скриптом.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Как зафиксировать ручной коммит в ссылку документов, чтобы amend-tests не счёл его инцидентом (record_fixation) — нашёл по отказу.
