# Записка test_author

## Выяснено
- Планка: acceptance_tests/test_ac2_ac3_ac8_ac9_child_row_write.py (разовый, в процессе: cmd_canary_run_task с шпионами insert/db/time.sleep), test_ac4_parent_prints_unwritten_row.py (разовый, зелёный с рождения), test_ac6_group_signal_without_grandchild.py (разовый: вложенный прогон настоящего GroupSignalTest с подменой protection._GRANDCHILD), test_ac1_race_assertion_message.py и test_ac7_race_files_change_scope.py (разовые, AST рабочей копии против `git show DIFF_BASE:` из _pult; общий код — _race_tests.py).
- AC-5 — долгоживущий tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py (неравенство констант canary/liveness).
- AC-2/3/4/8/9 разовые потому, что критерии требуют подмен закрытых имён canary — в долгоживущем файле это запрещено.
- Валидация стабом (повторы в except CanaryInterrupted + сообщения + правка run_cli/read_grandchild_pid): все 8 тестов планки, долгоживущий и оба существующих файла зелёные; мутации «store.db вне try» и «sleep между попытками» краснеют. Стаб откатан (`git checkout`), рабочая копия чиста, кроме нового долгоживущего файла.
- На текущем коде: AC-2/3/8/9 красны (OperationalError всплывает), AC-1 красен (нет сообщения), AC-5 — AttributeError, AC-6 — таймаут 120 с; AC-4 и AC-7 зелёные с рождения.
- preflight: все проверки пройдены.

## Не сработало
- Bash с `cd …;` или `$f` в цикле отклоняется песочницей — по одной команде, абсолютные пути.

## Где остановился
- Готово к сдаче.

## Чего не хватило
- docs/codebase-map.md после добавления tests/*.py не регенерирована: правку вне tests/ пульт на этом шаге откатил бы — регенерирует разработчик.
