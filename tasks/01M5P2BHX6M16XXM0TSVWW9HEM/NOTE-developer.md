# Записка developer

## Выяснено
- Реализация — `_print_table` в orchestrator/mutation_run.py, вызывается в трёх
  ветках `_wait` (есть отчёт / процесс умер без отчёта / время вышло) до прежнего
  текста; нет файла в ветке «ещё идёт» — «таблица ещё не начата».
- Долгоживущий файл задачи + tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py:
  27 passed; plank-run: 1 passed. Карта регенерирована.

## Не сработало
- Bash отказывает командам с `$VAR` («simple_expansion») — пути писать буквально.

## Где остановился
Готово, PLAN status: ready, guard ок.

## Чего не хватило
Ничего.
