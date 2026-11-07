---
task: 01M6TRM2EKZJV2FXP6C5YNE9FC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Мерж не ждёт CI main под замком: цвет main сверяет следующий мерж, идущий CI main он дожидается

## Фаза A: план
- Таблица покрытия PLAN закрывает требования 1–5; шаги (код, два теста по мандату, карта) — размер MR.
- Подход (перенос цикла из `_await_main_ci` в новый `_await_running_main_ci`, вызываемый из `_refuse_if_main_red` после ветки `--fixes-main`) не спорит с архитектурой: вызов `_refuse_if_main_red` стоит под мьютексом (`orchestrator/fsm_merge_gate.py:1582`, захват замка `:2055`), до плотницкого merge.
- «Влияние на систему» совпадает с diff: `orchestrator/fsm_merge_gate.py`, два метода `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` + импорт `patch_sleep`, карта. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_await_main_ci`: `send_pending()`, одно чтение `ci.main_line_status`, запись `MAIN_CI_AFTER_MERGE_ACTION` с четырьмя исходами; на идущем — «идёт — цвет сверит следующий мерж»; на неизвестном сохранено «не дождался» (нужно `tests/test_main_ci_line.py:324,327`). Цикла и паузы нет. |
| 2 | OK | `_await_running_main_ci`: `send_pending()` до первого опроса, `start = time.monotonic()` от начала этого ожидания, проверка предела → пауза `VERIFYING_POLL_INTERVAL_SEC` → `touch_heartbeat` → чтение. Зелёный — проход, красный — прежний отказ в `_refuse_if_main_red`, неизвестный — сразу возврат и прежний проход с записью «сверка CI main», предел — `sys.exit` «CI main <sha> не завершён за 18 мин — повтори approve» + «merge FAILED», задача на гейте. |
| 3 | OK | Записи «ожидание CI main» (начало, с sha) и «ожидание CI main: исход» (с sha) в журнале задачи этого мержа. |
| 4 | OK | Ветка `fixes_main` стоит раньше вызова ожидания: return без паузы, основание в журнале. |
| 5 | OK | Ранние выходы по `repo_context.is_artel` в обеих функциях не тронуты. |

Тесты: долгоживущий файл задачи `tests/test_01m6trm2ekzjv2fxp6c5yne9fc_main_ci_wait.py` закрывает AC-1…AC-9, `Группа: долгоживущий` уместна (свойства кода), у каждого метода «Ловит мутацию» с наблюдаемым расхождением. Сверка с базой `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`: изменены только два метода «Меняемого поведения» (мандат ANSWER-1) и импорт; прежние утверждения сохранены — в первом опрос новой головы после второго мержа и строка вывода о зелёном CI, во втором окно `WAIT_MIN_SEC`…20 мин с тем же `slack`; замена «не дождал» → «не завершён» совпадает с требованием 2. Новые утверждения первого теста — пп. 1–4 SPEC (запись «цвет сверит следующий мерж», начало и исход ожидания с sha, >1 опроса и пауза, `done`); второй — отказ, `merge_gate`, origin/main не сдвинут. Сужения данных под неизменными утверждениями не нашёл: `pending_polls` поднят с 1–3 до 2–4 по записке SPEC — это нужно, чтобы второму `approve` осталось «идёт», а не ослабление.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6trm2ekzjv2fxp6c5yne9fc_main_ci_wait.py tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py tests/test_main_ci_line.py tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py` — 45 passed, 14 subtests passed (383 с).
- `artel.py plank-run 01M6TRM2EKZJV2FXP6C5YNE9FC` — отказ «планки нет»: в зафиксированной планке нет test_*.py, все тесты задачи долгоживущие и лежат в `tests/`; pytest пультом не запускался.
- Временная мутация 1: убрал `artifact_branch.send_pending()` в `_await_running_main_ci` → `test_ac9_docs_ref_synced_when_main_wait_polls` красный. Код вернул.
- Временная мутация 2: `if False and status.kind == ci.MAIN_RUNNING` в `_refuse_if_main_red` (идущий CI — проход без ожидания) → красные AC-2, AC-3, AC-4, AC-7, AC-8, AC-9 (6 из 9; AC-1, AC-5, AC-6 и должны остаться зелёными). Код вернул, `git status` чистый.
- `python3 scripts/codebase_map.py` — карта по содержимому свежая (разница только в `built_at_sha`); изменение отменил `git checkout -- docs/codebase-map.md`.

## Предложения системе
- `scripts/codebase_map.py` не знает `--help`/`--check`: вызов с `--help` молча перегенерирует карту в рабочей копии. Режим `--check` (как в CI-джобе) избавил бы ревью от лишней записи в дерево.
