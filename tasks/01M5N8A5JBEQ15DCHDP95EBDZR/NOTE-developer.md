# Записка developer — 01M5N8A5JBEQ15DCHDP95EBDZR

## Выяснено
- Итерация 2 закрыла REVIEW итерации 1 (оба помечены fixed в реестре):
  - R1-F1: `_flush_pending` — попутный пропуск правки конфигурации идёт раньше,
    проверка `HELD_BASE_KEY`/`NO_BASE_WARNING` теперь ДО разделения на
    пакет/конфигурацию, поэтому явный флаш снова предупреждает.
  - R1-F2: `_flush_batch`, `except OSError` — `reset` + `_restore_tree` по
    `_target_rel(request)`.
- Новый тест `tests/test_notes_batch_flush_edges.py` (3 метода, на стенде
  `SuiteGateSandbox`); обе мутации проверены — красные, код возвращён.
- 8 файлов note/doc-commit + долгоживущий файл задачи: 136 passed, 11 subtests.
- Карта перегенерирована.

## Не сработало
- Многооперационные Bash (cp; heredoc python) требуют подтверждения — мутации
  делал через Edit.

## Где остановился
- Шаг завершён, PLAN.md status: ready (шаг 4 в PLAN описывает итерацию 2).

## Чего не хватило
- `scripts/guard.py` на файле tests/ ругается на frontmatter — гонять его только
  на артефактах; заявки мутации проверял `guard.test_functions_without_mutation_claim(None, src)`.
