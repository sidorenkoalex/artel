---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Одна функция открытия БД пульта только на чтение вместо пяти копий

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–5 сопоставлены шагам 1–3.
- Шаги размера MR (функция + db_usable; четыре вызывающих; карта и прогон).
- Подход совпадает с архитектурой: вызов через атрибут модуля `store.db_readonly`
  (нужно для шпиона AC-6), проверки/перехваты остаются у вызывающих.
- «Влияние на систему» соответствует diff: изменены ровно 5 файлов зоны
  (+ карта), `tests/` — только два долгоживущих файла test_author; гейты/лимиты не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/store.py:325-338`: `config.DB` читается в теле при `path is None`; `sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)` через атрибут модуля; `row_factory` только при `rows`; без `is_file`, без `except`, без `db()`. |
| 2 | OK | `store.db_usable` → `db_readonly(rows=False)` внутри прежнего `try/except sqlite3.Error` (store.py:353); `knowledge_cards.py:767`, `suite_run.py:179`, `preflight.py:84` → `store.db_readonly()`; `scripts/test_rule_stats.py:73` → `store.db_readonly(path=db_path, rows=False)` внутри `try`. Проверки `is_file()` и тексты отказов на месте. |
| 3 | OK | `grep -rn "mode=ro" orchestrator scripts`: вне `store.db_readonly` — только докстринги/комментарии (artel.py:2177/2179 — комментарии, остальное — докстринги). Линтер AC-4 зелёный. |
| 4 | OK | Два долгоживущих файла test_author держат AC-1…AC-7; докстринг AC-4 несёт требуемую заявку дословно. |
| 5 | OK | Существующие тесты не правлены (`git diff 55d469fd -- tests/` — только два новых файла); тесты команд из «Не входит» зелёные. Импорт `sqlite3` в вызывающих остался нужным (`sqlite3.Error`, аннотации) — лишних импортов не образовалось. Для `journal` прежний `sqlite3.connect(uri, uri=True)` без `row_factory` ↔ `rows=False` — эквивалентно. |

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider` по файлам: `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py`, `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py`, `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`, `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`, `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`, `tests/test_preflight.py`, `tests/test_test_rule_stats.py`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`, `tests/test_reference_command.py` — 88 passed, 119 subtests passed (34 с).
- `artel.py plank-run 01M5MHVFQ9SC6EDRH34F8THNQ3` — отказ «планки нет: в refs/artifacts/… нет файлов test_*.py»: у задачи только долгоживущие тесты в `tests/`, они прогнаны выше.
- `grep -rn "mode=ro" orchestrator scripts` — вне `store.db_readonly` только докстринги и комментарии.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — 0 строк расхождения (карта свежа); файл возвращён `git checkout`.
- `git diff 55d469fd --stat -- . ':!tasks' ':!docs/codebase-map.md'` — 5 файлов зоны + 2 новых теста, ничего вне зон.

## Предложения системе
- `artel.py plank-run` на задаче, где test_author сдал только долгоживущие файлы `tests/`, отвечает отказом «планки нет»; бриф ревьювера при этом велит гонять планку именно им — стоит в таком случае прогонять перечень лока (`orchestrator/role_prompt.py`/plank-run).
