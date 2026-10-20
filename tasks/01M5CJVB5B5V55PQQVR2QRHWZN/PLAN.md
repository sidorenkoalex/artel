---
task: 01M5CJVB5B5V55PQQVR2QRHWZN
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G3а-1а: гейт неослабления по исходам на выходе из `in_dev`

## Подход
Новый модуль `orchestrator/advance_gates/outcome_integrity.py` с обёрткой
`_outcome_integrity_gate_refuses(conn, task_id, t, artifact_branch)` той же
формы, что соседи; вызов в `fsm_advance.in_dev` сразу после
`_test_integrity_gate_refuses` и до `_review_rework_gate_refuses`.

- Граница: `t["is_canary"]`, `decide(target)` с отказом/пропуском или
  `not in_outcome_bounds(profile)` — `None` без git, прогона и журнала.
- Выписки: `gitcmd.diff_base` / `gitcmd.branch_head_sha` в клоне задачи
  (`workspace.task_repo`), `git worktree add --detach` во временный каталог
  (образец `two_sided.run`), уборка в `finally`. Любой сбой — `_Prepare` →
  отказ «… — подготовка» с причиной.
- Полный набор: `acceptance.components_full_suite(tree, id, (profile,),
  fresh=True)` на каждой выписке; «не начат/неизвестно» и таймаут — отказ
  подготовки с названной стороной («база» / «голова ветки»); «нет тестов» —
  пустой список записей.
- `PASS_TO_PASS` — `passed` с `retries == 0` на базе; красный на ветке —
  `failed`/`error`/`passed` с повтором. Перепрогон — по файлам красных тестов,
  2 раунда × (ветка, база) через `acceptance._report_run(profile, tree,
  [файл], component_limit)`; итог — по записи теста (правила требования 3).
- `compare(base, head)` — чистая функция над `CaseResult` (требование 4),
  одна находка на идентификатор; `skip_growth` — итоговая строка отказа.
- Мандат — `test_integrity._answer_mandate` (с отбраковкой автокоммита
  роли), покрытие `covering`: путь файла либо префикс `путь::имя` с `::`,
  `[`, `#` или концом за ним.
- Отказ: непокрытые находки по старшинству (исчез → сломан → нестабилен →
  прочие, внутри — по id), строка на находку; только «сломан правкой» —
  действие «… — сломан правкой», иначе общее. Пройденный гейт — запись
  «гейт неослабления по исходам пройден» с числами и строками «нестабилен и
  на базе: <id>».
- `refusal_classes.REFUSAL_CLASSES` — три действия; новый метод в
  `tests/test_refusal_classes.py`.

## Шаги
1. Модуль гейта, вызов в `fsm_advance.in_dev`, три действия в
   `REFUSAL_CLASSES`, юнит-тесты `tests/test_outcome_integrity.py`, метод
   `test_outcome_integrity_actions_have_their_spec_class`, карта кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 |

## Влияние на систему
- Гейт исполняется только у профиля `components:` с `report` из одного
  компонента; артель, `test_profile`, канарейка — прежний путь, вызов
  возвращает `None` до любого git (`tests/test_fsm_advance_gate_smoke.py`
  не тронут и зелёный).
- Цена — два полных прогона набора компонента и перепрогоны на каждом
  входе в переход (принятая цена до G3а-2, SPEC «Не входит»).
- Существующие гейты, тесты и лимиты не ослабляются; в
  `tests/test_refusal_classes.py` только добавлен метод. Долгоживущие тесты
  прежних задач (`tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`)
  зелёные без правок — подготовка в них не добавлялась (требование 8).
- Откат — revert одного merge-коммита: модуль новый, правка `fsm_advance` —
  одна строка вызова и импорт.

## Риски
- Выписки `git worktree add` в клоне проекта: при обрыве процесса между
  `add` и `finally` остаётся запись worktree (как у `two_sided`).
- `_report_run` — закрытая функция `acceptance`, вызывается так же, как в
  `two_sided._run_side_report` (SPEC называет её прямо).

## Предложения системе
- `python3 -m pytest -n 8` в шаге роли валит всех воркеров xdist («node
  down: Not properly terminated») — долгоживущий файл задачи пришлось
  гонять последовательно (3,5 мин).
