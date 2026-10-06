---
task: 01M49B90T16AR81ETFEYY164H1
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: CI ветки задачи — полный набор tests/ один раз на sha

# ТЗ: CI ветки задачи — полный набор tests/ один раз на sha

Источник: 06.10, анализ прогонов тестов (строка бэклога «CI ветки задачи —
полный набор один раз на sha», приоритет 1; строка копилки 06.09 о том же).
Каждый push ветки `task/**` с открытым черновиком PR запускает workflow
`ci` дважды — на событие `push` и на событие `pull_request`, — и задания
полного набора `python` и `python-min` идут в обоих прогонах: у части 3
этапа 3 ADR-0021 (01M484RNV3) шесть полных прогонов CI на три коммита.
Решение Оператора 06.10: завести.

Факты (пин d75f27ae, сверка кода 06.10):
- `.github/workflows/ci.yml`: триггер `push` на ветки `main` и `task/**`,
  триггер `pull_request` без фильтра. Задания `python` (~179) и
  `python-min` (~232) идут на обоих событиях (условие только
  `needs.changes.outputs.code != 'false'`); шаг наложения приложений PLAN
  (`scripts/plan_appendix_ci.py`, ~206 и ~253) — на обоих событиях для
  веток `task/`; `id-format-greplint` (~53) и `protected-paths` (~264) —
  только на `pull_request`. Фильтры `paths`/`paths-ignore` в триггере
  запрещены (ADR-0016, инвариант 36): лишние проверки снимаются условием
  на задании (статус `skipped`).
- `orchestrator/ci.py`: `verifying_status` (~487) и `branch_status` (~628)
  читают все check-run'ы коммита; `skipped` засчитывается зелёным
  (`ci.GREEN`); различие событий для текста — `_run_event` (~395),
  `_event_divergence` (~412, SPEC 01M46D5ZZQ); `find_run_id` (~950)
  выбирает прогон для ре-рана среди двух событий.
- `orchestrator/github_adapter.py` (~146): первый push кодовой ветки идёт
  до `gh pr create` — у первого push PR ещё нет; черновик PR заводится
  сразу после.
- `.github/workflows/ci.yml` — защищённый путь: правка только приложением к
  PLAN, его применяет Оператор.

Требуется:
1. На один head-коммит ветки `task/**` с открытым PR задания полного
   набора (`python`, `python-min`) выполняются один раз — в прогоне
   `pull_request`; в прогоне `push` той же ветки они `skipped`. Как CI
   узнаёт, что у ветки есть PR, — решение SPEC (условие на задании, шаг
   запроса API, иное), без фильтров `paths` в триггере. Push ветки без PR
   (первый push до `gh pr create`, ветка, PR которой закрыт) гоняет полный
   набор, как сегодня. `main` не меняется.
2. Ожидание CI пультом (`verifying`, гейт мержа, `approve`) не засчитывает
   зелёным коммит, у которого полный набор есть только `skipped` в
   прогоне `push`, а прогона `pull_request` ещё нет или он не завершён:
   нужное задание обязано завершиться хотя бы в одном прогоне. Fail-closed:
   событие не определилось — ждать, как сегодня.
3. Ре-ран (`find_run_id`, `trigger_rerun`) нацеливается на прогон, где
   задание полного набора реально шло.
4. Изменение `ci.yml` — приложение к PLAN с точным текстом; проверка
   приложения (`plan_appendix_ci.py --check-workflow`) проходит.
5. Тесты в `tests/` с заявками «Ловит мутацию»: коммит с `skipped`
   полным набором в push и без прогона pull_request — не зелёный; тот же
   коммит с завершённым pull_request — зелёный; ре-ран выбирает прогон
   pull_request; push без PR — полный набор считается нужным. Существующие
   тесты не ослабляются.
6. В PLAN — замер по истории Actions: число прогонов `python` на коммит
   ветки до (по последним задачам) и ожидаемое после.

Зоны: orchestrator/ci.py, scripts/ci_push_class.py, tests/,
docs/codebase-map.md.

Приложением: .github/workflows/ci.yml

Только чтение (не менять): orchestrator/github_adapter.py,
scripts/plan_appendix_ci.py, conftest.py,
tests/test_invariants.py, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/, CLAUDE.md,
models.yaml, roles.yaml, targets.yaml.

Не входит: CI ветки `main`; повторное использование итогов полного
прогона на гейтах пульта (задача 01M48WT5X7); автогейт по зелёному CI
(строка бэклога A4); время одного прогона CI.

Рамка: $30.
