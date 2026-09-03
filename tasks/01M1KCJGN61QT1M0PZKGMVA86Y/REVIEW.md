---
task: 01M1KCJGN61QT1M0PZKGMVA86Y
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 3
---

# REVIEW: CR-2 — тихая финализация соединения БД из чужого потока

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (перехват `sqlite3.ProgrammingError` в `__del__`, не пробрасывается, не печатается) | OK | `orchestrator/store.py:96-100` — узкий `try/except sqlite3.ProgrammingError: pass` вокруг `self.close()`. |
| 2 (перехват узкий — только `ProgrammingError` в месте `close()`) | OK | Подтверждено тестом `acceptance_tests/test_ac1_narrow_exception_scope.py::test_ac1_other_exception_from_close_is_not_swallowed` — `RuntimeError` пробрасывается наружу. |
| 3 (закрытие из своего потока не меняется, T090-тест зелёный без правок) | OK | `acceptance_tests/test_ac3_inline_thread_test_unchanged.py` сверяет исходник теста байт-в-байт (`inspect.getsource`) и его прохождение — оба зелёные. |
| 4 (тест кросс-поточной финализации без «Exception ignored» в stderr) | OK | `acceptance_tests/test_ac2_cross_thread_finalization.py` — реальный `gc.collect()` из другого потока с `redirect_stderr`, корректно решает проблему переиспользования id потока после `join()` (держит поток-создатель живым до завершения финализатора). |
| 5 (все существующие тесты зелёные) | OK | `acceptance_tests/test_ac4_full_suite_green.py` гоняет `tests/` подпроцессом и проверяет код возврата; независимо перепроверено вручную (см. «Проверено исполнением»). |

## Замечания

- minor — tests/test_store_db_connection_close.py:37-40 — докстринг нового теста `test_del_swallows_programmingerror_from_foreign_thread_close` описывает сценарий, но не несёт обязательной заявки `Ловит мутацию: …` (skills/test-authoring.md, требование review-checklist п.3) — в отличие от всех четырёх приёмочных тестов (`tasks/01M1KCJGN61QT1M0PZKGMVA86Y/acceptance_tests/test_ac*.py`), где заявка присутствует и корректна. Предложение: дописать во второй абзац докстринга явную формулировку `Ловит мутацию: удаление try/except вокруг self.close() в __del__ — тогда conn.__del__() в отдельном потоке пробросит sqlite3.ProgrammingError вместо тихого возврата`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | open | tests/test_store_db_connection_close.py:37-40 | докстринг нового теста без заявки «Ловит мутацию: …» | будущий ревьювер/разработчик не может свериться, какую мутацию тест обязан ловить, вопреки конвенции test-authoring | дописать заявку «Ловит мутацию: …» в докстринг |

## Вердикт
changes_requested

Дефектов класса blocker/major не найдено — по существу реализация
узкая, точно соответствует SPEC/PLAN, риск из PLAN («Риски»)
подтверждён на практике: `sqlite3.Connection.close()` идемпотентен
(не бросает при повторном вызове — см.
`test_explicit_close_then_gc_does_not_raise`), единственный случай
`ProgrammingError` в этой точке — межпоточный запрет, ровно предмет
CR-2. Диф ограничен заявленной в PLAN «Влиянием на систему» зоной
(`orchestrator/store.py` тело `__del__`, `tests/`, приёмочные тесты,
`docs/codebase-map.md`) — сверх этого ничего не задето (`git diff
--stat main...HEAD`). `docs/codebase-map.md` меняет только
`built_at_sha` (легитимно per skill, содержимое идентично).

Формально по severity (0 blocker/major) это тянуло бы на `approved`,
но реестр (R2-F1, статус `open`) при schema_version 3 механически
блокирует гейт `review -> verifying` независимо от severity —
несу `changes_requested`, чтобы не подавать вердикт, который гейт
молча отклонит. Исправление тривиально (одна строка в докстринге) —
после правки R2-F1 в реестре следующая итерация сразу закрывается.

## Проверено исполнением
- `python3 -m unittest discover -s tasks/01M1KCJGN61QT1M0PZKGMVA86Y/acceptance_tests -v` — 11 тестов (AC-1×2, AC-2×1, AC-3×2, AC-4×1, плюс существующие T090-тесты, задетые импортом) — все `ok`, `Ran 11 tests ... OK`, 152.5s.
- `python3 -m unittest discover -s tests` (полный набор, независимо от AC-4) — `Ran 1307 tests in 153.958s`, `OK`; `grep -c "Exception ignored" <лог>` — 0 вхождений (против заявленных в SPEC/PLAN 28 строк шума до правки — CR-2 фактически устранена).
- `git diff --stat main...HEAD` — состав изменённых файлов совпадает с заявленной зоной PLAN («Влияние на систему»): `orchestrator/store.py`, `tests/test_store_db_connection_close.py`, `docs/codebase-map.md`, артефакты `tasks/01M1KCJGN61QT1M0PZKGMVA86Y/*`; сторонних side effects нет.
- `git diff main...HEAD -- docs/codebase-map.md` — единственная строка диффа `built_at_sha`, содержимое карты не изменилось.
- Прочитаны все 4 файла `tasks/01M1KCJGN61QT1M0PZKGMVA86Y/acceptance_tests/test_ac{1,2,3,4}_*.py` целиком и тело `_AutoClosingConnection` (`orchestrator/store.py:74-100`) — вручную сверены с требованиями и критериями приёмки SPEC.

## Предложения системе
- Ревью-пакет этой итерации был выдан с `iteration: 2` и sha
  предыдущего вердикта `00e32aaf2c15059ffb72260275b29b9d2b53e8fe`,
  но этот sha не резолвится в репозитории (`git cat-file -t` —
  `fatal: could not get object info`), и `git log -- REVIEW.md` для
  этой задачи пуст — файла REVIEW.md в истории ветки не было вовсе.
  Похоже на генерацию пакета до появления первого REVIEW.md реальной
  задачи, либо на устаревший/чужой sha, просочившийся в шаблон
  пакета. Расследовал вручную по инструкции скила («Инкрементальный
  diff пакета — пустой не значит…») — итог: полный `main...HEAD` diff,
  вердикт этой итерации построен как будто первой.
- review-checklist внутренне расходится для minor-замечаний при
  schema_version >= 3: секция «Вердикт» велит `0 blocker/major →
  approved` (значит, minor не блокирует), а секция «Реестр замечаний»
  п.4 велит не нести `approved`, пока в реестре есть хоть одна не-
  `accepted` запись — а любое заведённое замечание (в т.ч. minor)
  обязано попасть в реестр как `open`. На практике единственный
  непротиворечивый выбор для ревьювера, нашедшего ровно один minor-
  дефект, — `changes_requested`, хотя по букве «Вердикта» это должен
  быть `approved`. Стоит явно прописать в «Вердикте», что при
  schema_version >= 3 гейт реестра имеет приоритет над правилом
  severity, либо разрешить не заводить реестровую запись для minor,
  которую ревьювер не считает блокирующей.
