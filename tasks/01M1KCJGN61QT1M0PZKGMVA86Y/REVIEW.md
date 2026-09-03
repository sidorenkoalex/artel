---
task: 01M1KCJGN61QT1M0PZKGMVA86Y
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: CR-2 — тихая финализация соединения БД из чужого потока

## Фаза A: проверка плана
PLAN.md покрывает оба требования шагами разумного размера (2 шага,
13 строк кода + 1 юнит-тест), таблица покрытия требований полна и
верна (все 5 требований SPEC закрыты шагами 1–2). Подход (узкий
`try/except sqlite3.ProgrammingError` вместо дублирования проверки
`threading.current_thread()`) не конфликтует с существующей
архитектурой — обоснование отклонения альтернативы разумно (не
дублировать критерий, который уже проверяет сам sqlite3). Секция
«Влияние на систему» соответствует фактическому diff (проверено ниже,
Фаза B, п.6). Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (перехват ProgrammingError, не пробрасывается, не печатается) | OK | orchestrator/store.py:96-100; подтверждено AC-1/AC-2 исполнением |
| 2 (перехват узкий) | OK | `test_ac1_other_exception_from_close_is_not_swallowed` подтверждает: `RuntimeError` не глушится |
| 3 (закрытие из своего потока не меняется, T090-тест зелёный без правок) | OK | AC-3: исходник теста байт-в-байт совпадает (`test_ac3_source_of_existing_test_method_is_unchanged`), тест зелёный |
| 4 (тест кросс-поточной финализации без «Exception ignored» в stderr) | OK | AC-2, зелёный, стабилен на 3 повторных прогонах |
| 5 (все существующие тесты зелёные) | OK | полный прогон `tests/`: 1307 тестов, OK, 0 вхождений «Exception ignored» в stderr (было 76 до правки, по свидетельству docstring AC-4-теста) |

## Замечания

- minor — tests/test_store_db_connection_close.py:37-40 — докстринг нового теста
  `test_del_swallows_programmingerror_from_foreign_thread_close`
  описывает сценарий, но не несёт обязательной заявки `Ловит
  мутацию: …` (конвенция skills/test-authoring.md, требование
  Фазы B п.3 review-checklist) — все остальные новые/изменённые
  тесты этого MR (оба теста в
  tasks/.../acceptance_tests/test_ac1_narrow_exception_scope.py, тест
  в test_ac2_cross_thread_finalization.py, оба теста в
  test_ac3_inline_thread_test_unchanged.py, тест в
  test_ac4_full_suite_green.py) такую заявку несут — это единственный
  пропуск, класс исчерпан диффом полностью. Без заявки ревьювер не
  может сверить тест с конкретной ожидаемой мутацией, а опирается на
  интуицию, что и запрещает чек-лист. Предложение: добавить строку
  вида «Ловит мутацию: удаление `try/except` вокруг `self.close()` в
  `__del__` (возврат к простому `self.close()`) — тогда
  `conn.__del__()`, вызванный из чужого потока, поднимет
  `sqlite3.ProgrammingError` вместо тихого возврата».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_store_db_connection_close.py:37-40 | докстринг нового теста без заявки «Ловит мутацию: …» | ревьювер не может сверить тест с заявленной мутацией на будущих итерациях; нарушение конвенции test-authoring.md | добавить строку «Ловит мутацию: …», описывающую откат перехвата в `__del__` |

## Вердикт
`changes_requested`. Единственная находка — minor, конвенционная
(отсутствие заявки «Ловит мутацию:» в докстринге одного нового теста).
Сама реализация корректна, узость перехвата подтверждена тестом,
регрессий нет, полный набор тестов зелёный. По правилу «Гейт
вердикта» реестра замечаний approved не пройдёт, пока в реестре есть
запись со статусом отличным от `accepted` — R1-F1 сейчас `open`,
поэтому вердикт этой итерации `changes_requested`, а не `approved`,
несмотря на то что находка одна и minor. После добавления строки
«Ловит мутацию:» в докстринг (без изменения остального кода/тестов)
задача готова к аппруву.

## Проверено исполнением
- `python3 -m unittest tests.test_store_db_connection_close -v` —
  5 тестов, все `ok` (включая новый
  `test_del_swallows_programmingerror_from_foreign_thread_close` и
  неизменённый T090-тест
  `test_no_resourcewarning_when_connection_is_used_inline_and_discarded`).
- `python3 -m unittest tasks.01M1KCJGN61QT1M0PZKGMVA86Y.acceptance_tests.test_ac1_narrow_exception_scope tasks.01M1KCJGN61QT1M0PZKGMVA86Y.acceptance_tests.test_ac2_cross_thread_finalization tasks.01M1KCJGN61QT1M0PZKGMVA86Y.acceptance_tests.test_ac3_inline_thread_test_unchanged -v`
  — 10 тестов, все `ok` (AC-1, AC-2, AC-3 подтверждены).
- `test_ac2_gc_in_foreign_thread_does_not_print_exception_ignored`
  (AC-2) прогнан отдельно ещё 3 раза подряд — стабильно `ok`, флейка
  не обнаружено.
- `python3 -m unittest discover -s tests` (AC-4, полный набор) —
  «Ran 1307 tests in 144.594s», «OK»; `grep -c "Exception ignored"`
  по захваченному выводу (stdout+stderr) — 0 вхождений.
- `python3 scripts/codebase_map.py` (перегенерация карты) —
  сравнение с закоммиченной docs/codebase-map.md показало разницу
  только в строке `built_at_sha` (карта содержательно свежая); после
  проверки локальная перегенерация отменена (`git checkout --
  docs/codebase-map.md`), рабочее дерево чистое.
- `git show 8a0b498 --stat` — подтверждено, что коммит, на который
  указывает закоммиченный `built_at_sha`, сам содержит правку
  `orchestrator/store.py` и регенерацию карты тем же коммитом
  (конвенция соблюдена).

## Предложения системе
(пусто)
