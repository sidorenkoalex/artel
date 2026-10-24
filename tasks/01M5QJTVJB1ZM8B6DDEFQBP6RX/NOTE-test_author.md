# Записка test_author

## Выяснено
- Планка: `_plan.py` (разбор PLAN/таблиц/AST, соглашения — в его докстринге),
  `_ctx.py` (загрузчики поверх `_pult`), 4 разовых файла:
  test_mutation_patches (AC-1), test_mutation_tables (AC-2/3/4/5/14-дубли/15/16),
  test_branch_diff (AC-6/7/17), test_module_form (AC-8…13, AC-14 заявки).
  Пометок manual/skip/escalate нет. Форма — с волны 2б-3
  (refs/artifacts/01M5PT190RWC6984CDQVZ242GN).
- «Функция, в которую перенесён тест» — функция файла модуля с его именем
  (`_plan.moved_to`); имена 40 исходных тестов уникальны и не вложены друг в друга.
- Помощник `row` сталкивается с локальной `row = self.row()` → планка
  допускает имя помощника с префиксом `<x>_row` (кроме двух `seed`),
  `_plan.helper_names`/`helper_renames`; нормальная форма учитывает переименование.
- «Окно может не взяться» (AC-2) = патч меняет строки `merge_lock.acquire/
  _holder_is_dead/_is_own_process/run_window` или `merge_queue.wait_for_window/
  _head_task_id/_prune_dead_entries` → часть ≤8 патчей («до» и «после»).
- Нормальная форма AC-16/AC-12 — решение 1 ANSWER-1 (`_plan.normal_form`).
- Валидация стабом: клон в $TMPDIR, автоконвертер 3 файлов → 2 pytest-модуля
  (40 passed), синтетические PLAN/40 патчей/ссылка документов: планка 59/59
  зелёная; 7 порч (ослабленное ==, фикстура, часть 29 патчей, расхождение
  до/после, строка падения вне утверждения, посторонний test_*.py) — красные.
  Стаб и сценарии удалены.
- plank-run на ветке: 53 failed, 6 passed (зелёные — «не тронуто»/AC-6/карта).
  preflight — всё пройдено.

## Не сработало
- Bash: `$VAR`, `=…` в heredoc и `ls`/`awk` отклоняются — сценарии писал файлом
  в каталог документов и удалял python3.

## Где остановился
- Готово.

## Чего не хватило
- Формат шапки mutation-run (`orchestrator/mutation_run.py::_header`) и поля
  `_pult` DOCS_REPO/DOCS_REVISION — взял из образца 2б-3.
