# Записка developer — 01M5MVSP9YW0DYA4YQ1KSG0AHF

## Выяснено
- Шаг 2 (возврат с рубежа in_dev -> verifying): красный один тест — test_ac2_plan_appendix.py::test_ac2_lint_class_green_with_appendix, «git apply: patch failed: tests/test_invariants.py:39».
- Причина — несовместимость залоченного теста с деревом пульта: appendix_tree.suite_tree накладывает приложения на файлы временного дерева БЕЗ коммита; тест решает «накладывать ли» через _pult.apply_check, а та проверяет HEAD (read-tree HEAD + apply --check --cached, plank_helper.py:139–147). HEAD без приложения → тест накладывает повторно на уже наложенные файлы → отказ.
- Приложение PLAN == приложению SPEC побайтно; git apply --check на чистом дереве ветки проходит (после подтяжки main 5cbcc4bd тоже).
- Код задачи (test_lint.py, guard.py, amend.py) в ветке, коммит 4f30324d; остальные 25 тестов планки/долгоживущих зелёные.
- Сравнение на дереве tests/ (шаг 1): 658 файлов, 62 ключа, побайтно равны.

## Не сработало
- Кодом не чинится: единственный обход — закоммитить приложение в защищённый tests/test_invariants.py, роли запрещено.
- Bash с `$VAR` в команде отклоняется («simple_expansion») — писал пути целиком.

## Где остановился
- PLAN.md status: escalate, раздел «Эскалация» (дефолт — amend-tests теста: признак «уже в дереве» брать по диску копии, не по HEAD). guard ок. Кода в этом шаге не менял.

## Чего не хватило
- Что дерево прогона планки на рубеже несёт приложения незакоммиченными, а _pult.apply_check смотрит на HEAD — узнал из appendix_tree.py:272–288 и plank_helper.py:139.
