---
task: 01M3PKSWPETC49WFTFZ69GH3F2
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Канарейка исполняет код проверяемого коммита, а не код пина (ADR-0021, этап 0)

## Фаза A — план

- Со времени итерации 1 план по существу не менялся. Добавлены только отчёт итерации 2 (мутации R1-F1..R1-F3) и новые тесты в перечне. Таблица покрытия требований 1–8 полна, шаги по размеру соответствуют MR, подход согласован с архитектурой (выводы итерации 1 в силе).
- «Влияние на систему» соответствует диффу итерации: `orchestrator/canary.py::_drive_in_clone` (окружение процесса и ветка прерывания) и `tests/test_canary_drive.py`. Вне зоны ничего не тронуто.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Процесс `-m orchestrator.canary_drive`, `cwd` — клон, результат пишется в файл `--result`. Порядок в `drive()` теперь держит сторож `CanaryDriveMainTest.test_drive_opens_the_task_then_worktree_then_drives_it` |
| 2 | OK | `build_result` без изменений с итерации 1 |
| 3 | OK | Без изменений с итерации 1 |
| 4 | OK | `_ephemeral_clone`, `_run_verdict`, `_baseline_deviation_note` не тронуты |
| 5 | OK | Строку сводки с обоими коммитами держит `CommitMismatchSummaryTest` |
| 6 | OK | Без изменений с итерации 1 |
| 7 | OK | При прерывании (`except BaseException`, canary.py:1956-1962) группа процесса клона снимается, прерывание пробрасывается дальше. `PYTHONUNBUFFERED=1` (canary.py:1942) — буфер вывода при снятии не теряется |
| 8 | OK | Существующие файлы `tests/` не изменены. В `tests/test_canary_drive.py` только добавления и параметр `flush` у сценарного входа, ассерты не удалялись |

## Замечания

Blocker и major нет.

Для сведения, не замечание: SIGTERM, посланный пульту (обработчика у пульта нет, `grep signal.signal` по `canary.py`/`artel.py` пуст), убивает процесс без исключения Python. Группа клона тогда переживает пульт. До задачи было так же: `finally` клона не исполнялся, и шаги ролей тоже переживали пульт. Значит, это не регрессия задачи. Ctrl-C и `SystemExit`, о которых говорил R1-F1, закрыты.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/canary.py:1956-1962 | Прерывание пульта не снимало группу процесса клона | Агенты работали бы на удалённом клоне | Принято: ветка `except BaseException` снимает группу, ждёт лидера и пробрасывает прерывание. Мутация `BaseException`→`ZeroDivisionError` красит `InterruptedPultTest` |
| R1-F2 | accepted | orchestrator/canary_drive.py:64; orchestrator/canary.py:2209 | Нет сторожа в `tests/` у ведения в `drive()` и у строки расхождения в сводке | После мержа CI не поймал бы поломку | Принято: обе мутации итерации 1 (удалён `_drive_task`, условие → `if False:`) красят `CanaryDriveMainTest.test_drive_opens_…` и `CommitMismatchSummaryTest` |
| R1-F3 | accepted | orchestrator/canary.py:1942 | Буферизованный вывод терялся при снятии по таймауту | Диагностика зависания пуста | Принято: `PYTHONUNBUFFERED=1`. Мутация (переменная переименована) красит `test_output_of_a_killed_process_is_not_lost_in_its_buffer` |

## Вердикт

`approved`. Все три замечания итерации 1 исправлены, и сторожа проверены временными мутациями. Новых blocker/major нет.

## Проверено исполнением

- `python3 -m pytest -q tests/test_canary_drive.py` — 19 passed, 4 subtests.
- Временные мутации, каждая прогонялась на `tests/test_canary_drive.py`, после каждой код возвращён `git checkout -- orchestrator/`, `git status` чист, кроме `tasks/`:
  - `except BaseException` → `except ZeroDivisionError` (canary.py:1956): красный `InterruptedPultTest` (1 failed);
  - `"PYTHONUNBUFFERED"` → `"PYTHONXX"` (canary.py:1942): красный `test_output_of_a_killed_process_is_not_lost_in_its_buffer` (1 failed);
  - удалён `canary._drive_task(conn, task_id)` (canary_drive.py:64) и условие расхождения заменено на `if False:` (canary.py:2209): красные `CanaryDriveMainTest.test_drive_opens_the_task_then_worktree_then_drives_it` и `CommitMismatchSummaryTest` (2 failed). В итерации 1 те же мутации давали 163 passed.
- `python3 -m pytest -q tasks/01M3PKSWPETC49WFTFZ69GH3F2/acceptance_tests tests/test_canary.py tests/test_canary_budget_ceiling.py tests/test_canary_codex_clone_auth.py tests/test_canary_synthetic_answer.py tests/test_canary_template_flag.py tests/test_canary_sets.py tests/test_pin.py` — 245 passed, 14 subtests (92 с).
- `git diff 0fc59406..HEAD --stat -- tests/` — изменён только `tests/test_canary_drive.py`. Удалённые строки — шаблон сценарного входа (`flush`) и сигнатура `commit()`, ассерты не удалялись. У каждого нового метода есть «Ловит мутацию: …» с наблюдаемым расхождением.
- CI коммита 7d0bcc48 зелёный (из пакета).

## Предложения системе

- Итерация 1 предлагала отметку Оператора для чужой залоченной планки 01M1SC3Y20YBTTJVQDJBF2NDQW: после мержа она станет заведомо красной. Предложение в силе.
