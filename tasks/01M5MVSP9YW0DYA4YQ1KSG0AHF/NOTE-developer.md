# Записка developer — 01M5MVSP9YW0DYA4YQ1KSG0AHF

## Выяснено
- orchestrator/test_lint.py — дословный перенос; сравнение на дереве tests/ (658 файлов): 62 ключа и там и там, побайтно равны.
- Приложение 1 из SPEC: git apply --check проходит; с ним DeterministicTestsLintTest 6 passed, 16 subtests. tests/test_invariants.py в worktree НЕ правлю (защищённый путь — применяет пульт).
- guard: lint_errors_from_files(files, lint_base) + вызов в long_lived_errors_from_files до plank_file_group. amend.py: _plank_lint_errors (метки acceptance_tests/…), _locked_plank_lint_base, _locked_long_lived_texts/_text_with_digest (--from-branch). Три долгоживущих файла задачи зелёные (23 теста).
- by_rule-пути amend не трогал: у артели правило планки всегда по умолчанию (project_profile.plank_rule), у чужого проекта линта нет.
- Тесты затронутых модулей (19 файлов amend/long_lived/preflight/test_groups/network) — 283 passed. Карта регенерирована.
- PLAN status: ready, guard ок. Приложение вставлено скриптом из SPEC (побайтно).

## Не сработало
- plank-run: AC-2 красный только потому, что PLAN.md читается из ссылки документов, а туда он попадает автокоммитом после шага. Проверки AC-2 на тексте с диска (равенство блоков, «ключ»+число, test_lint.findings) прошли.
- pytest -n 4 в рабочей копии — «node down»; гонял без -n.

## Где остановился
- Шаг завершён: код в worktree незакоммичен (коммитит пульт).

## Чего не хватило
- Что plank-run читает PLAN из ссылки документов, а не с диска, — узнал по красному AC-2.
