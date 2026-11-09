---
task: 01M6YHH891Z3ZM464M1D0RK2ZB
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Ускорение тестов suite_run без ослабления — уборка без ожидания своего процесса, меньшие пределы, шаг опроса из config, проверка процессов вместо пауз

## Фаза A: план
- Таблица покрытия полна: требования 1–9 → шаги 1–2, строка AC-10 (ANSWER-3) → шаг 3.
- Шаг 3 — проверяемая единица (два усиления одного файла по мандату ANSWER-3), не микрооперация.
- «Влияние на систему» совпадает с диффом итерации: `git diff 55aef548f..HEAD` — только
  `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` (+13/−4) и строка `built_at_sha` карты.
  Мутации `mutation-001.diff` (acceptance.save_suite_result) и `mutation-002.diff`
  (suite_run.parse) лежат вне строк, которые меняет задача. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: `config.SUITE_RUN_POLL_SEC = 1.0`, `_POLL_SEC` удалена, `wait_request`/`_wait`/`mutation_run._wait` читают config в момент паузы; держит долгоживущий `test_01m6yhh891z3zm464m1d0rk2zb_poll_step.py` (3 passed). |
| 2 | OK | Копия config песочницы: `SUITE_RUN_POLL_SEC = 0.1`. |
| 3 | OK | `pids.discard(os.getpid())` после цикла сбора. |
| 4 | OK | `TIMEOUT_SEC = 8` у трёх классов, ac16 гейт — 3 с. |
| 5 | OK | `assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)`. |
| 6 | OK | ac24 без изменений с итерации 1. |
| 7 | OK | Снимок `ps` → журналы; ac21 щадит `holder` и потомков по `ppid` только для пробы/корня. |
| 8 | OK | Итерация 2 (ANSWER-3): ac16 гейт — `full_suite(..., command=[str(self.python), "-m", "pytest"])`, финальный счёт `before + 1` вместо абсолютной 1; ac11 — `phrase_number(out, "прошло:"/"упало:") == P+1/F` добавлено, `standalone` оставлен. Прежние утверждения не сняты. Дополнительный `assertEqual(len(self.base_calls()), 1)` сразу после гейта — усиление: без него обход обёртки гейтом снова делает мутацию «сохраняет итог при таймауте» невидимой (до задачи было именно так, ANSWER-3 матрица, строка 1). Паузы ac6/ac8 не тронуты; 26 тестов, skip нет. |
| 9 | OK | `mutation_run_flags` зелёный в итерации 1, код с тех пор не менялся (дифф итерации — только тестовый файл); CI коммита 0de9c2ef зелёный (16 проверок). |

## Замечания
Нет замечаний уровня blocker/major/minor.

Наблюдения для Оператора (к указанию на гейте SPEC; не изменились с итерации 1):
- Указание 3: ac24 строит путь лога базы из лога ветки в выводе запуска (`launched`) с суффиксом
  `-base`, а не из `run.json`; отчёт `--wait` не используется, промах пути даёт красный тест.
- Указание 1: код выхода `ps` отдельно не сверяется — провал держится на наличии строки
  `os.getpid()` в снимке.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет (в итерации 1 записей не было).

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6YHH891Z3ZM464M1D0RK2ZB` — 8 passed in 1.92s, код выхода 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py tests/test_01m6yhh891z3zm464m1d0rk2zb_poll_step.py` — 29 passed, 6 subtests passed за 240,6 с серийно.
- Временные мутации: `git apply` `mutation-001.diff` + `mutation-002.diff` (обе `git apply --check` OK),
  `pytest … -k "ac16_timed_out_gate or ac11"` — 2 failed: ac16 гейт «1 != 2 : база не прогнана после
  таймаута гейта» (:1090), ac11 «числа 6 нет» (:860). `git apply -R`, `git status --short` пусто.
- `git diff 55aef548f..HEAD -- docs/codebase-map.md` — меняется только `built_at_sha`.

## Предложения системе
- Пакет ревью не смог определить базу инкрементального diff итерации 2 («журнал фиксации не несёт
  её») — дифф итерации пришлось снимать вручную от sha CI прошлого вердикта (`55aef548f..HEAD`).
