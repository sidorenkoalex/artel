---
task: 01M1KCJGN61QT1M0PZKGMVA86Y
type: spec
author_role: analyst
status: ready
schema_version: 3
budget_usd: 10
---

# SPEC: CR-2 — тихая финализация соединения БД из чужого потока

## Контекст
Ревизия кода (docs/audits/code-revision-2026-09-02.md, находка CR-2)
зафиксировала, что деструктор автозакрывающегося соединения
(`orchestrator/store.py`, класс `_AutoClosingConnection`, наследие
T090) бросает `sqlite3.ProgrammingError`, когда сборщик мусора
добивает объект из другого потока, не создавшего соединение: 28 строк
«Exception ignored … SQLite objects created in a thread…» за прогон
полного набора тестов. Закрытие соединения из чужого потока
невозможно по ограничению самого sqlite3 — оно и так штатно достаётся
сборщику мусора, — но текущая реализация не глушит это конкретное
исключение, и шум маскирует настоящие предупреждения (мотивация той
же природы, что и CR-3 прошлой ревизии).

## Требования
1. `_AutoClosingConnection.__del__` перехватывает `sqlite3.
   ProgrammingError`, возникающий при попытке закрыть соединение из
   потока, отличного от создавшего его, — исключение не
   распространяется наружу и не печатается в stderr как «Exception
   ignored».
2. Перехват узкий: ловит только `sqlite3.ProgrammingError` в месте
   вызова `close()` внутри `__del__`; любое другое исключение,
   возникшее там же, не глушится.
3. Закрытие соединения из СВОЕГО потока продолжает работать как
   сейчас: `ResourceWarning` не возникает (существующий тест
   `tests/test_store_db_connection_close.py::
   DbConnectionAutoCloseTest::test_no_resourcewarning_when_connection_is_used_inline_and_discarded`
   остаётся зелёным без изменений).
4. Добавлен тест, воспроизводящий финализацию из чужого потока:
   соединение создаётся в одном потоке, ссылки на него отпускаются, а
   сборка мусора добивается объекта в другом потоке; прогон не
   печатает «Exception ignored» в stderr.
5. Все существующие тесты остаются зелёными.

## Критерии приёмки
AC-1. `_AutoClosingConnection.__del__` (orchestrator/store.py) обёрнут
узким перехватом `sqlite3.ProgrammingError` вокруг вызова `close()`;
любое другое исключение в этом месте перехватом не гасится.

AC-2. Тест: соединение создано в одном потоке, ссылки на него сняты, а
сборка мусора (`gc.collect()`) объекта выполнена в ДРУГОМ потоке —
прогон не печатает «Exception ignored» в stderr.

AC-3. Тест `tests/test_store_db_connection_close.py::
DbConnectionAutoCloseTest::test_no_resourcewarning_when_connection_is_used_inline_and_discarded`
(закрытие из своего потока, T090) остаётся зелёным без изменений
поведения.

AC-4. Полный прогон `tests/` зелёный.

## Не входит
- Ревизия потоковой модели соединений `orchestrator/store.py`.
- Изменение механики автозакрытия T090 (`_AutoClosingConnection`
  остаётся тем же классом с тем же назначением, меняется только
  обработка исключения в `__del__`).

## Материалы
- docs/audits/code-revision-2026-09-02.md, находка CR-2.
- orchestrator/store.py:74-90 (`_AutoClosingConnection`).
- tests/test_store_db_connection_close.py (T090, существующий тест
  ResourceWarning).
- Зависимость по времени исполнения (не по содержанию SPEC): задача
  запускается строго после мержа A7 (01M1H224X5A8W159MKF1Q24R5Y) —
  на момент написания этого SPEC A7 уже смержена в main (коммит
  2ca44d6), `orchestrator/store.py` свободен.
