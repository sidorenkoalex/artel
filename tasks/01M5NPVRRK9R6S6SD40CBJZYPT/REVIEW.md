---
task: 01M5NPVRRK9R6S6SD40CBJZYPT
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Прогон планки после подтяжки main — на дереве с приложениями PLAN

## Фаза A: план
- Таблица покрытия полна (требования 1–6 → шаги 1–2); шаги — размера MR.
- Подход повторяет образец рубежа `in_dev -> verifying`
  (`orchestrator/advance_gates/acceptance.py:597–616`: `suite_tree` → отказ по
  `tree.fixable` → `plank_in_code_copy`), конвенциям не противоречит.
- «Влияние на систему» = diff: изменён только `orchestrator/pull.py`
  (`_materialize_and_run_plank` + импорт `contextlib`) и карта. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/pull.py:686–712`: `suite_tree(conn, task_id, wt_path, not_run=…)`; при `tree.root != wt_path` — `plank_in_code_copy(task_id, artifact_branch_name, tree.root)` в том же `ExitStack`; при `tree.root == wt_path` — прежние `tdir`/`cwd=wt_path`, материализация с `preexisting` (строки 617–622, `finally` 717–719) не тронута. |
| 2 | OK | `tree.root is None` → журнал `PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION`/`PLAN_APPENDIX_GATE_FAILURE_ACTION` по `tree.fixable` с `tree.refusal`, `Refused(tree.refusal)`, без `set_state`, без прогона. Путь `pull-main` (вне зоны) не тронут. |
| 3 | OK | Проверки «планка не найдена», «перечень не прочитан», `ComponentsPending` — выше дерева, тексты и порядок прежние; дерево строится сразу перед `acceptance.run`. |
| 4 | OK | Тексты красного итога/`Pulled` не менялись; `green`/`tail` читаются после выхода из `ExitStack` (дерево уже снято — корректно, нужны только значения). |
| 5 | OK | Долгоживущий файл `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py` (test_author) покрывает AC-1–AC-7, у каждой функции «Ловит мутацию:» с наблюдаемым расхождением. |
| 6 | OK | `git diff --stat` — `tests/` не тронуты (кроме долгоживущего файла лока). |

## Замечания

Блокирующих и major нет.

- minor — `orchestrator/pull.py:701` — ветка `run_cwd, run_tdir = wt_path, tdir` при `tree.root == wt_path` и выкладка в рабочую копию выше выполняются всегда, даже когда затем прогон уходит во временное дерево (материализация в рабочую копию «вхолостую»). Это осознанно по SPEC (требование 3: порядок проверок «планка не найдена» прежний, она опирается на материализацию) — не дефект, к сведению.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Записей нет: единственное minor — информационное, без требуемого действия.)

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py tests/test_pull.py -p no:cacheprovider -q` — 26 passed, 7 subtests passed (14.6 с).
- `artel.py plank-run 01M5NPVRRK9R6S6SD40CBJZYPT` — отказ «планки нет … нет файлов test_*.py»: планка целиком долгоживущая (только перечень), её файл прогнан выше напрямую.
- Временная мутация 1: `if tree.root != wt_path:` → `if False:` (прогон всегда в рабочей копии) — долгоживущий файл: 6 failed (ac1, ac4, ac5 оба подслучая, ac6, ac7), 3 passed. Код возвращён `git checkout`.
- Временная мутация 2: `if tree.fixable:` → `if True:` (одно действие для обоих классов) — `test_ac3` подслучай «сбой git» красный. Код возвращён, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha`, карта свежая; регенерация откачена.

## Предложения системе
- `plank-run` для планки, целиком долгоживущей (только `long_lived.sha256.txt`), отказывает «планки нет» и не гоняет долгоживущие файлы перечня — ревьювер и разработчик гоняют их `pytest` напрямую (`orchestrator/plank_run.py`); то же отметил PLAN.
