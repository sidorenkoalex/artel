# Записка test_author

## Выяснено
- ANSWER-1 п.1: точка входа `_tests_writing_fail_to_pass_gate(conn, task_id, acc_tdir, run_cwd, covered, profiles)` в orchestrator/advance_gates/tests_writing.py. Имя закрытое, поэтому прямой вызов — в разовом файле планки `acceptance_tests/test_direct_gate_two_components.py` (долгоживущему импорт `_x` из orchestrator запрещён).
- Он импортирует песочницу `FailToPassSandbox` модулем из tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py (`ftp.FailToPassSandbox`, чтобы pytest не собирал её второй раз).
- У записи из двух компонентов поле `paths` обязательно у каждого компонента (targets.py:438).
- Пометки escalate AC-9/AC-12 сняты: в markers.py теперь только докстринг. Комментарии и докстринг долгоживущего файла про эскалацию поправлены.
- Новый файл: 3 метода (AC-9 пустой список по компоненту файла ×3 подслучая, AC-9 списки по компоненту файла в находках, AC-12 правило не построено). Красны: функции нет. Со временным стабом гейта все зелёные; стаб откатил через git checkout.
- preflight: все проверки пройдены.

## Не сработало
- `rm`/`cat` в Bash недоступны: markers.py не удалён, а переписан.

## Где остановился
Готово: в планке не осталось ни одной пометки escalate, preflight зелёный.

## Чего не хватило
- Обязательность `paths` у записи из нескольких компонентов: выяснил только по TargetsError.
