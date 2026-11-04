---
task: 01M6KB0FS809DG55K9A20CYKJE
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Предел числа процессов шага роли

## Фаза A: план
- Таблица покрытия полна, в ней требования 1–9. Шаг 4 PLAN дополнен итерацией 2: добавлен `tests/test_role_nproc_step.py` со сторожами поведения шага (R1-F1).
- «Влияние на систему» совпадает с diff: после итерации 1 добавлен один файл, `tests/test_role_nproc_step.py`. Код `orchestrator/` не менялся, защищённые пути не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. Передачу `nproc_limit` в каждую попытку теперь сторожит `test_step_passes_role_limit_to_every_attempt`. |
| 2 | OK | Однократное предупреждение при `failed` и его отсутствие при `absent` сторожат `test_failed_read_warns_once_per_step` и `test_absent_maxproc_writes_no_warning`. |
| 3 | OK | Отказ при N = M, отсутствие агента и захвата зоны сторожит `test_exhausted_reserve_refuses_without_agent_and_zone_claim`. Сбой счёта сторожит `test_count_failure_warns_once_and_step_runs`. |
| 4 | OK | Без изменений; держит долгоживущий AC-2. |
| 5 | OK | Порядок «снятие до `close_pump`» и запись только при непустой группе сторожит `GroupLeftoverTest`. |
| 6 | OK | Без изменений с итерации 1. |
| 7 | OK | Карта свежа: регенерация меняет только `built_at_sha`. |
| 8 | OK | Приложение в PLAN без изменений. |
| 9 | OK | Новые тесты не порождают процессов: агент — `FakeProc`, а `terminate_process_group` подменён. |

## Замечания
Новых замечаний нет. Тесты `tests/test_role_nproc_step.py` несут заявки «Ловит мутацию» с наблюдаемым расхождением. Каждую заявку я проверил временной мутацией (см. «Проверено исполнением»). Тесты не повторяют долгоживущий файл задачи: тот держит `spawn_agent` и `role_nproc_limit` на настоящем процессе, а новые тесты — поведение шага через `cmd_run`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_role_nproc_step.py (новый) | Поведение шага (отказ, однократные предупреждения, передача `nproc_limit`, снятие группы) сторожила только разовая планка | После мержа регрессия прошла бы незамеченной | Закрыто: 7 тестов покрывают пункты (а)–(г). Семь временных мутаций `runner.py` окрашивают тест каждая (`>=`→`>`, `leftover = 0`, снятая передача из `_run_attempts`, `failed`→`!= ok`, неловимое исключение счёта, снятое предупреждение, запись без проверки `leftover`). |
| R1-F2 | accepted | orchestrator/runner.py `_step_nproc_limit`; orchestrator/doctor/role_nproc.py | `_read_maxprocperuid` зовётся дважды | Лишний `sysctl`; теоретическое расхождение текста предупреждения | Отказ разработчика принят. SPEC (Р-2, О-5, AC-1, AC-7) требует, чтобы шаг и `doctor` звали саму `role_nproc_limit()`. Цена — миллисекунды. Расхождение текста возможно только при нестабильном `sysctl`, и предел при этом не выше верного. Замечание minor. |

## Вердикт
approved — реестр закрыт, blocker и major нет.

## Проверено исполнением
- `python3 -m pytest tests/test_role_nproc_step.py tests/test_role_nproc_limit.py tests/test_01m6kb0fs809dg55k9a20cykje_role_nproc.py -p no:cacheprovider -q` — 17 passed.
- Временные мутации `orchestrator/runner.py` (скрипт подменял строку, гонял `tests/test_role_nproc_step.py` и восстанавливал файл), по одной за прогон:
  - `count >= limit` → `>` — 1 failed;
  - `leftover = 0` — 2 failed;
  - снят `nproc_limit=` в вызове `run_agent_once` из `_run_attempts` — 1 failed;
  - `outcome == "failed"` → `!= "ok"` — 1 failed;
  - `except Exception` → `except ZeroDivisionError` в счёте — 1 failed;
  - снята запись `NPROC_WARNING_ACTION` при `failed` — 1 failed;
  - `if leftover:` → `if True:` — 1 failed.

  После прогона `git status --short` пуст, код восстановлен. Скрипт мутаций удалён командой `task-rm`.
- `artel.py plank-run 01M6KB0FS809DG55K9A20CYKJE` — 27 passed, код выхода pytest 0.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md`: изменилась только строка `built_at_sha`, карта свежа; файл возвращён `git checkout`.

## Предложения системе
- Тот же скрипт мутаций в `/tmp` отклоняется правами шага, а inline `python3 - <<EOF` с f-строками режет фильтр «brace with quote». Ревьюверу пришлось класть скрипт в каталог документов и убирать его `task-rm`. Штатная команда пульта «временная мутация» (подмена → прогон файлов → откат) сняла бы эту возню (`orchestrator/artel.py`, skills/review-checklist.md «Сторож — проверен временной мутацией»).
