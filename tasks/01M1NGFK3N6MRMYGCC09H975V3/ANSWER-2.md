---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. Задача ВОЗВРАЩЕНА из verifying: CI кодовой ветки красный (коммит
   231a7e0a, джоб «Синтаксис и тесты оркестратора»):
   `tests/test_gitcmd_check_ignore.py::DiffNamesTest::test_lists_changed_paths`
   — `Lists differ`, в списке изменённых путей появляются
   `.artel/state.db`, `.artel/state.db-shm`, `.artel/state.db-wal`. На main
   этот тест зелёный; на ветке адресный прогон зелёный, красно только в
   полном прогоне CI. Вывод «менять нечего» неверен: ветка вносит утечку
   изоляции между тестами.
2. Где искать: новые тесты задачи (`tests/test_pin.py`, `tests/test_doctor.py`
   новые классы, `tests/test_gitcmd_branch_reads.py`) вызывают
   `store.db()`/`store.create_schema(store.db())` — часть классов без
   подмены `config.ROOT`/пути БД (строки с `self.conn = store.db()` без
   `patcher`). БД пульта создаётся в реальном корне чекаута CI (там
   `.artel/` нет в git, но файлы появляются на диске) и попадает в
   репозиторий-фикстуру соседнего теста через `git add -A`. Требование:
   каждый новый тест подменяет `config.ROOT` и путь БД на временный
   каталог (образец — `tests/sandbox.py`, инвариант 33 «тесты не пишут в
   настоящий репозиторий пульта»), после теста в чекауте не остаётся
   `.artel/`.
3. Воспроизведение: чистый чекаут без `.artel/`, один процесс:
   `python3 -m unittest tests.test_pin tests.test_doctor
   tests.test_gitcmd_branch_reads tests.test_gitcmd_check_ignore`, затем
   `ls -la .artel/` — каталог не должен появиться. Приёмка — зелёный CI
   ветки.
