---
task: 01M49B90T16AR81ETFEYY164H1
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: CI ветки задачи — полный набор tests/ один раз на sha

## Фаза A: план

- Таблица покрытия полна (требования 1–8), шаги проверяемые.
- Изменение подхода после возврата приёмки 07.10: шаг `open-pr` ставит
  `open_pr=true` только при явных `state=open` и `mergeable=true` в карточке PR.
  Это закрывает дыру: у конфликтующего PR GitHub не запускает `pull_request`, а без
  проверки полный набор пропал бы на обоих событиях, и коммит навсегда завис бы в
  `verifying`. Обработка `null`, `false`, пустого ответа, сбоя и таймаута
  fail-safe: набор остаётся на push. Это согласуется с требованием 2.
- «Риски» честно называют цену: лишний прогон, пока `mergeable=null`, и при
  одновременных первом push и открытии PR. Инвариант 36 не задет: `paths` нет.
- «Влияние на систему» = diff: `orchestrator/ci.py` с итерации 2 не менялся.
  Инкремент `27ccce74..6638bc26` — только новый `tests/test_ci_workflow_mergeable.py`.
  `.github/` ветки не тронут.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Задания `python`/`python-min`: на `pull_request` идут всегда, на push с `open_pr=true` — `skipped`. Шаг ограничен `push` + `refs/heads/task/`. |
| 2 | OK | Без PR, при несливаемом PR и при сбое API `open_pr` пуст, набор идёт на push. На `main` шаг не исполняется: условие задания то же, что раньше. |
| 3 | OK | Код пульта не менялся с итерации 2. Долгоживущий файл задачи — 126 passed в составе затронутых модулей. |
| 4 | OK | Без изменений, AC-10 зелёный. |
| 5 | OK | Приложение из текущего PLAN: `git apply --check` — 0, `plan_appendix_ci.py --check-workflow` — 0. |
| 6 | OK | Свойства AC-4…AC-14 держит долгоживущий файл. Новый тест сторожит условие workflow (сливаемость, ветка `task/`, условия заданий); заявки проверены мутациями, см. ниже. |
| 7 | OK | Замер 2 → 1 на коммит (01M484RNV3) с оговоркой о недоступном `gh run list`; принят в итерации 1. |
| 8 | OK | `ci.FULL_SUITE_CHECKS` — единственное объявление. |

## Замечания

Блокирующих и major-замечаний нет.

Наблюдения, не замечания:
- `tests/test_ci_workflow_mergeable.py` читает `ci.yml` с наложенным приложением.
  На голом дереве ветки он красный (`ValueError: '      - id: open-pr' is not in
  list`). В CI зелёный, потому что шаг `plan_appendix_ci.py` накладывает приложение
  до pytest (`ci.yml` ~199–206). После мержа зелёный, когда Оператор наложит
  приложение. Это та же механика, что у остальных тестов задачи под приложение.
  Разработчик описал локальный обход переменной `ARTEL_TEST_WORKFLOW`.
- Мутация «убрать `.state == "open"` из jq карточки» тестом не ловится: фейковый
  `timeout` проверяет состояние сам. Тест её и не заявляет. Последствий нет: список
  уже запрошен с `state=open`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Открытых записей нет: R1-F1 принят (`accepted`) в итерации 2, новых замечаний нет.

## Вердикт

approved. Ужесточение шага `open-pr` по сливаемости PR корректно и fail-safe.
Новый тест действительно ловит заявленные мутации. Код пульта и долгоживущие тесты
не менялись и зелёные.

## Проверено исполнением

- `python3 -m pytest -q tests/test_ci_workflow_mergeable.py` на голом дереве ветки:
  2 failed (`ValueError`, шага `open-pr` нет). Ожидаемо, без наложения приложения.
- Приложение извлечено из текущего PLAN.md и наложено на копию `ci.yml` во
  временном каталоге: `git apply --check` — 0, `git apply` — 0,
  `python3 scripts/plan_appendix_ci.py --check-workflow <копия>` — 0
  («шаг приложений PLAN есть в jobs python, python-min»).
- `ARTEL_TEST_WORKFLOW=<копия> pytest tests/test_ci_workflow_mergeable.py`:
  2 passed, 9 subtests.
- Временные мутации копии `ci.yml` (код ветки не трогался):
  - убрать `and .mergeable == true` — 3 failed (false/null/closed);
  - заменить GET карточки на `mergeable=$number` — 5 failed;
  - условие `python` без `open_pr` — 1 failed;
  - шаг без `startsWith(github.ref, 'refs/heads/task/')` — 1 failed;
  - убрать `.state == "open"` — зелёный (не заявлено, см. наблюдения).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M49B90T16AR81ETFEYY164H1`:
  1 passed, код выхода pytest 0.
- `pytest -q tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py tests/test_ci_status.py tests/test_ci_rerun_command.py tests/test_ci_push_class.py`:
  126 passed, 126 subtests passed.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md` без
  `built_at_sha`: расхождений нет, карта свежая. Регенерация откачена, `git status`
  чистый.
- `git diff --stat main -- .github orchestrator/ci.py`: `.github/` не тронут,
  изменён только `orchestrator/ci.py`.
- CI коммита 6638bc26 зелёный (16 проверок) — по статусу из пакета. Он включает
  новый тест на дереве с наложенным приложением.

## Предложения системе

- Вспомогательный скрипт мутаций ревьювера (`.review_mut.py`) пришлось положить в
  каталог документов задачи: однострочный bash с `$VAR` отклоняется песочницей,
  а `rm` недоступен. Удалить его роль не смогла, и он попадёт в артефактную ветку.
  Нужен временный каталог роли вне артефактов, либо разрешённая уборка
  собственных файлов в каталоге документов.
