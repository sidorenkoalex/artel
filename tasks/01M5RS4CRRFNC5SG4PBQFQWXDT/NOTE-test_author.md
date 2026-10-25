# Записка test_author

## Выяснено
- Планка готова: `acceptance_tests/` — `_plan.py` (разбор PLAN/таблиц + AST-преобразования), `_ctx.py` (загрузчики над `_pult`), `test_mutation_patches.py` (AC-1), `test_mutation_tables.py` (AC-2,3,4,5,15-дубли,16,17,18), `test_module_form.py` (AC-7…15), `test_branch_diff.py` (AC-6, AC-19). Все разовые; долгоживущих файлов нет.
- Образец — планка волны 2а-2б (`refs/artifacts/01M5RH875Q1JMVRM1TXNE6HNMW`), адаптирована: сокращение файла вместо удаления, 22 теста 14 классов, помощники passed/grant/conftest_case, развёртка subTest (`_plan.converted_test`), предел части 10 при `рабочих процессов: 4`, убийство только чужими классами — не доказательство, `grant` — подготовка.
- Сообщения passed/grant — `case +` спереди прежнего выражения (ANSWER-1 п. 1); refusal/no_gate_refusal сверяются полным `ast.dump` с функциями tests/test_outcome_gate_module.py (включая докстринг).
- Цикл подслучаев сверяется как цикл (развёрнутый в прямой код цикл AST-сверку не пройдёт).
- Валидация стабом (временный клон в $TMPDIR, сценарий удалён): свод, собранный `_plan.converted_test`/`converted_helper` + ast.unparse, — 109/109 зелёные при поддельном PLAN; сам модуль стаба — 22 passed (74,8 с). Мутации стаба (`runs > 0`, ярлык без зерна, строка падения в grant) красят заявленные тесты.
- plank-run на рабочей копии: 93 failed, 16 passed — краснота «нет HEAD:tests/test_outcome_prior_module.py / prior_outcome_sandbox.py», файл не сокращён (44 теста). preflight пройден.

## Не сработало
- Bash: `$VAR`, `;`-цепочки, `ls`/`sed`/`rm`, прямой путь к venv-python отклоняются; `python3` из PATH работает.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Ничего существенного.
