## Выяснено
- Все AC-1..AC-9 — свойства кода: один долгоживущий файл
  tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py, в acceptance_tests/ планки нет.
- Песочница SyncedOriginConnSandbox: целевой коммит пушится в origin, главная копия
  откатывается reset --hard HEAD~1; «пин сдвинут» = HEAD стал целевым sha.
- Часы: mock.patch.object(pin, "time", FakeClock, create=True) — единые часы
  (sleep двигает now, monotonic отдаёт now), старт — целое число (без ошибок float).
- До реализации: AC-6, AC-7 зелёные, остальные красные по правильной причине.

- «fetch не вызван» видно по remote-tracking ref: setUp откатывает
  refs/remotes/origin/main на старый sha, любой fetch вернёт его на целевой.
- Временный стаб (диспетчер + цикл ожидания) — 9/9 зелёные; мутации «N = прошедшее
  время», «> вместо >=», «fetch до отказа формы» ловятся. Стаб откачен.

## Не сработало
- `cat`/`ls` в Bash недоступны (нет PATH) — читать файлы через Read.
- Шпион на gitcmd.git: preflight отказывает долгоживущему файлу по признаку «git-модуль»
  (импорт gitcmd) — заменил проверкой ref.
- plank-run отказывает «планки нет» — в acceptance_tests/ нет test_*.py, это ожидаемо.

## Где остановился
- Готово: preflight пройден по всем проверкам.

## Чего не хватило
- Ничего.
