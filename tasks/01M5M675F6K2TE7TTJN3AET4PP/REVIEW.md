---
task: 01M5M675F6K2TE7TTJN3AET4PP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ссылки origin/task главной копии — уборка в pin-update; бесхозные каталоги .artel/worktrees — уборка командой prune

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–5 → шаги 1–4; шаги размера MR.
- Подход учитывает ANSWER-2 (п.1 формат `_remove_dirs`, п.2 уборка после
  `merge --ff-only`, п.3 N — разница `for-each-ref`, п.4 каталог с `.git`
  оставлен, п.5 имя закрытой задачи не защищает, п.6 оба вида сбоя) и
  ANSWER-3 (правка AC-5 через `amend-tests`, код не меняется).
- «Влияние на систему» совпадает с diff: `orchestrator/pin.py`,
  `orchestrator/prune.py`, `docs/retention.md`, новый
  `tests/test_pin_prune_orphan_guards.py`, карта. `cleanup.py`,
  `workspace.py`, `gitcmd.py`, `_remove_dirs`, существующие тесты не тронуты.
  Откат — revert мержа.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/pin.py:161` — `_prune_origin_refs()` последним вызовом после журнала «pin обновлён» и `_report_stale_cycles`; все отказы (fetch/канарейка/CI/merge) — `sys.exit` выше. Сбой (`None`/ненулевой код) — строка «уборка ссылок origin не выполнена: <причина>», без `sys.exit`. N — `len(before - after)` по ANSWER-2 п.3 (отступление от «строк `[pruned]`» SPEC авторизовано ответом). Вызов идёт через `gitcmd.git` без собственного таймаута. |
| 2 | OK | `orchestrator/prune.py:211–261`: кандидаты — каталоги не-ссылки, имя не id незакрытой задачи; перечни главной копии (`config.ROOT`) и клона (`workspace.repo(DEFAULT_TARGET)`) через собственный `_worktree_list`, различающий «не получен» (`None`) и пустой; любой `None` — вид пропущен. Нет кандидатов — git не зовётся. Каталог с `.git` оставлен (ANSWER-2 п.4). Удаление — существующий `_remove_dirs` (`shutil.rmtree`, по ссылкам не ходит). |
| 3 | OK | Строки плана/исполнения строятся одним `_print_report` с `log_verb`; сбой — прежний формат `_remove_dirs` (ANSWER-2 п.1, ANSWER-3); «нечего убирать» подавлено видом/«оставлен»/«пропущено»; прежние строки не изменены (вставка блока между «упразднённых механизмов» и диагностикой канарейки). |
| 4 | OK | `docs/retention.md`: оба раздела дополнены, фраза «`prune` этого вида не касается» удалена; планка AC-8 зелёная. |
| 5 | OK | Тесты на настоящем git (`SyncedOriginConnSandbox`, `RealGitSandbox`), подмены — только запуск git, CI, канарейка. |

## Замечания
Нет замечаний уровня blocker/major/minor.

Проверено и признано корректным:
- Тест разработчика `tests/test_pin_prune_orphan_guards.py` не повторяет
  долгоживущие файлы задачи: долгоживущий AC-3 держит только отказ по
  канарейке, тест разработчика — CI красный/неподтверждён и сбой
  `merge --ff-only` (ANSWER-2 п.2), а также п.4 и п.5, которых в
  долгоживущих нет. У всех методов есть заявки «Ловит мутацию» с
  наблюдаемым расхождением.
- Правка долгоживущего AC-5 (e1706759) — по ANSWER-3/ADR-0012
  (`amend-tests`): префикс строки сбоя приведён к формату `_remove_dirs`,
  проверка непустой причины и продолжения цикла сохранены — не ослаблено.
- Существующие тесты в diff не меняются.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний в итерации 1 нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py tests/test_pin_prune_orphan_guards.py tests/test_prune.py tests/test_pin.py tests/test_invariants.py::MainCopyGitUnchangedDuringTaskTest` — 32 passed, 11 subtests passed (40 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5M675F6K2TE7TTJN3AET4PP` — `test_ac8_retention_doc.py` 1 passed, код выхода pytest 0.
- Временная мутация `orchestrator/prune.py:257`: `os.path.lexists(path / ".git")` → `(path / ".git").is_dir()` — `tests/test_pin_prune_orphan_guards.py::OrphanWorktreeGitAndClosedNameTest::test_unregistered_dir_with_git_is_left_with_reason` красный (1 failed, 2 passed); код возвращён, `git status` чист.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (карта свежа по содержимому); регенерированный файл откатан `git checkout`.
- CI коммита e1706759 зелёный (16 проверок, из пакета).

## Предложения системе
- Пакет ревьювера: SPEC требование 1 («N — число строк `[pruned]`») уточнено ANSWER-2 п.3 («разница `for-each-ref`»), а заявка мутации долгоживущего AC-1 описана под первую формулировку. Пульт не отмечает такие расхождения SPEC↔ANSWER в пакете — ревьюверу приходится сводить их вручную; помогла бы сноска «требование N уточнено ANSWER-k п.m» прямо в SPEC пакета.
