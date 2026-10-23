---
task: 01M5K9M5DGPDRXG2M5B4KKGQ54
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: pin-update --wait-ci — ожидание CI головы main командой пульта

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–10 привязаны к шагам 1–3.
- Шаги размера MR (pin.py / artel.py / прогон), не микрооперации.
- Подход повторяет `fsm_merge_gate._wait_for_branch_ci_green` и константы гейта
  мержа — с архитектурой не конфликтует; файлы только для чтения из SPEC не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/artel.py:2040` `_cmd_pin_update`: sha — первый не-`--` аргумент, `wait_ci="--wait-ci" in rest`; `pin.cmd_pin_update(sha, wait_ci: bool = False)` (`pin.py:123`). |
| 2 | OK | `artel.py:2052-2054` — отказ формы до `cmd_pin_update`, т.е. без `fetch`/журнала; AC-8 зелёный. |
| 3 | OK | `artel.py:2048-2050` — прочий `--…` и второй sha → «неизвестный аргумент <арг>»; AC-9 зелёный. |
| 4 | OK | Ветка `else` зовёт прежнюю `_refuse_unless_main_ci_green` (`pin.py:140-143`), её тело не менялось; AC-6 и `tests/test_pin.py` зелёные. |
| 5 | OK | Ожидание стоит на месте `_refuse_unless_main_ci_green`, после `fetch` и гейта канарейки; AC-7 зелёный. |
| 6 | OK | `pin.py:97-120`: GREEN → return, RED → прежний текст, иначе печать строки → потолок `>=` с константой в тексте → `sleep(POLL)`; паузы после последнего опроса нет. |
| 7 | OK | `merge --ff-only` только после возврата на `MAIN_GREEN`; `cmd_pin_to` не тронут. |
| 8 | OK | Строка перечня `artel.py:190-191` (в стиле строк `canary --detach/--parallel`) и абзац `artel.py:303-306`. |
| 9 | OK | `import time` на уровне модуля `pin.py:52`; вызовы `time.sleep`/`time.monotonic` через него. |
| 10 | OK | Долгоживущий файл задачи: единые подменённые часы `FakeClock`, подмена через `mock.patch.object` в `with` (снимается в конце каждого вызова), без счётчика вызовов `monotonic`. |

## Замечания
Нет blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет — реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m5k9m5dgpdrxg2m5b4kkgq54_pin_update_wait_ci.py tests/test_pin.py tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` — 36 passed, 6 subtests passed.
- `artel.py plank-run 01M5K9M5DGPDRXG2M5B4KKGQ54` — отказ «планки нет» (в refs/artifacts нет `test_*.py`; приёмка задачи целиком в долгоживущем файле `tests/`), pytest не запускался.
- Временная мутация `pin.py:109` `== MAIN_GREEN` → «не RUNNING и не RED» (UNKNOWN = зелёный) — красный `test_ac2_unknown_is_not_green_on_wait_path`; код возвращён.
- Временная мутация `pin.py:116` `>=` → `>` — красный `test_ac5_ceiling_equal_to_period_refuses_after_second_poll`; код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` → diff `docs/codebase-map.md` только в строке `built_at_sha` — карта свежая; изменение откатил.
- `git diff 71ce9904...HEAD --stat -- tests/` — только новый файл задачи (346+), существующие тесты не тронуты, ассертов не удалено.
- CI коммита 4f79e209 — зелёный (16 проверок, из пакета).

## Предложения системе
- `plank-run` отказывает «планки нет», когда вся приёмка задачи ушла в долгоживущий файл `tests/`; ревьюверу полезна подсказка в тексте отказа, что приёмку держит долгоживущий файл из перечня лока.
