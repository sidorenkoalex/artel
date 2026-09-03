---
task: 01M1KCJGN61QT1M0PZKGMVA86Y
type: review
author_role: reviewer
status: approved
iteration: 3
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

(пусто — единственное замечание прошлой итерации, R2-F1, исправлено и
принято, см. «Реестр замечаний»; новых замечаний в инкрементальном
дифе не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | tests/test_store_db_connection_close.py:37-44 | докстринг нового теста без заявки «Ловит мутацию: …» | будущий ревьювер/разработчик не может свериться, какую мутацию тест обязан ловить, вопреки конвенции test-authoring | дописан абзац «Ловит мутацию: удаление try/except вокруг self.close() в __del__ — тогда conn.__del__() в отдельном потоке пробросит sqlite3.ProgrammingError вместо тихого возврата» в докстринг теста (коммит 02804ba) — заявка проверена: соответствует реальной мутации (удаление try/except в `orchestrator/store.py:96-100` действительно даёт пробрасывание `sqlite3.ProgrammingError` в чужом потоке), тест `test_del_swallows_programmingerror_from_foreign_thread_close` зелёный |

## Вердикт
approved

Инкрементальный диф (5291d9c..02804ba — реальный коммит вердикта
итерации 2, sha `00e32aaf2c15059ffb72260275b29b9d2b53e8fe` из пакета
снова не резолвится, см. «Предложения системе») содержит ровно
исправление R2-F1: докстринг `test_del_swallows_programmingerror_
from_foreign_thread_close` (tests/test_store_db_connection_close.py:
37-44) получил абзац «Ловит мутацию: …», плюс легитимное обновление
`built_at_sha` в docs/codebase-map.md (правка `.py`-файла требует
регенерации карты per conventions-core). Ничего другого не менялось —
`git diff --stat 5291d9c..02804ba` — три файла: REVIEW.md (статус
записи), tests/test_store_db_connection_close.py (докстринг),
docs/codebase-map.md (built_at_sha).

Заявка «Ловит мутацию» в исправленном докстринге проверена, а не
принята на слово: указанная мутация (удаление `try/except
sqlite3.ProgrammingError: pass` вокруг `self.close()` в `__del__`,
orchestrator/store.py:96-100) при реальном применении действительно
превращает тихий возврат в пробрасывание `ProgrammingError` из чужого
потока — ровно то, что тест и проверяет через мок `conn.close` и
запуск `conn.__del__()` в отдельном потоке.

Полный диф ветки (main...HEAD) не изменился по составу и содержанию
относительно того, что уже было одобрено по существу в итерации 2 (0
blocker/major, соответствие SPEC полное — таблица выше без изменений).
Реестр закрыт целиком (единственная запись R2-F1 → `accepted`) — гейт
`review -> verifying` пройдёт.

## Проверено исполнением
- `python3 -m unittest tests.test_store_db_connection_close -v` — 5 тестов, все `ok` (включая исправленный `test_del_swallows_programmingerror_from_foreign_thread_close`), `Ran 5 tests in 0.017s`, `OK`.
- `python3 -m unittest discover -s tasks/01M1KCJGN61QT1M0PZKGMVA86Y/acceptance_tests -v` — 11 тестов (AC-1×2, AC-2×1, AC-3×2, AC-4×1, плюс T090-тесты, задетые импортом) — все `ok`, `Ran 11 tests in 146.597s`, `OK`; AC-4 внутри прогоняет полный `tests/` подпроцессом и подтверждает зелёный код возврата.
- `git diff 5291d9c..02804ba` (реальный коммит вердикта итерации 2 → HEAD) — только 3 файла: REVIEW.md (статус R2-F1), tests/test_store_db_connection_close.py (докстринг +4 строки), docs/codebase-map.md (built_at_sha); `orchestrator/store.py` не менялся с итерации 2.
- `git diff main...HEAD --stat` — состав изменённых файлов не расширился относительно уже одобренной по существу в итерации 2 зоны (orchestrator/store.py, tests/test_store_db_connection_close.py, docs/codebase-map.md, tasks/01M1KCJGN61QT1M0PZKGMVA86Y/*); сторонних side effects нет.
- Прочитан `orchestrator/store.py:74-100` (`_AutoClosingConnection`) и полный текст исправленного докстринга — заявка «Ловит мутацию» сверена вручную с фактическим кодом перехвата.

## Предложения системе
- Sha предыдущего вердикта в этом пакете (`00e32aaf2c15059ffb72260275b29b9d2b53e8fe`) снова не резолвится в репозитории — тот же самый sha, что и в пакете итерации 2, хотя реальный коммит вердикта итерации 2 (`5291d9c`, статус `changes_requested`) теперь существует в истории. Поле «sha предыдущего вердикта» не обновилось между итерациями 2 и 3, несмотря на появление настоящего REVIEW.md-коммита между ними — расширяет наблюдение из «Предложения системе» итерации 2 (T082/T087, скил «Инкрементальный diff пакета…»): проблема не в отсутствии коммита-вердикта на момент сборки пакета, а в том, что сборка пакета, похоже, не подтягивает актуальный sha даже когда он уже есть. Расследовано вручную: `git diff 5291d9c..02804ba` (5291d9c найден через `git log --oneline -- tasks/01M1KCJGN61QT1M0PZKGMVA86Y/REVIEW.md`) — диф оказался узким и ожидаемым, но при менее очевидном случае (правка кода между вердиктами) тот же баг мог бы скрыть реальные изменения от ревьювера, доверившегося пакету.
