---
task: 01M1R9YEK08XEQWBFX0929WFVJ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: Приёмка и мерж читают артефакты из артефактной ветки (регрессия №12)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (планка approve `acceptance` — из артефактной ветки) | OK | `fsm.py:333-335` — `acceptance.materialize_from_branch` вместо `acceptance.run(wt_path/...)`; приёмочный тест AC-1 зелёный. |
| 2 (тот же источник в общем узле сверки свежести) | OK | Один и тот же узел `_pull_main_or_escalate` покрывает `in_dev->review`, `acceptance->merge_gate`, окно `merge_gate` — AC-2 зелёный. |
| 3 (merge_gate->done несёт снимок артефактной ветки) | OK | `fsm_merge_gate.py::_overlay_artifact_snapshot`, вызван после merge до `merge_sha`; AC-6/AC-7/AC-8/AC-11 зелёные. |
| 4 (CI guard не валидирует tasks/<id>/ на task/**) | реализовано не так — см. замечание R1-F1 | Diff `ci.yml` приложен к PLAN.md по протоколу защищённых путей (верно), `git apply --check` на текущем `main` (41ea4d4f) проверен мной — применяется чисто. Само требование 4 не относится к коду этой ветки. |
| 5 (существующее поведение не ослаблено) | реализовано не так — см. замечание R1-F1 | Новый путь чтения SPEC.md с артефактной ветки (требования 1-2) вводит РЕГРЕСС относительно установленной конвенции `_read_branch_text_or_refuse` — см. замечание. |

## Замечания

- blocker — `orchestrator/fsm.py:344-347` (и, как следствие, все четыре
  точки вызова `_pull_main_or_escalate`: `orchestrator/fsm.py:820-821`
  `_cmd_approve`/state `acceptance`, `orchestrator/fsm_advance.py:763-764`
  `in_dev`, `orchestrator/fsm_merge_gate.py:326-327`
  `_cmd_approve_merge_gate`, `orchestrator/canary.py:191-192`
  `_pass_acceptance_gate`) — чтение `SPEC.md` артефактной ветки для
  различения «планка не найдена легитимно» (AC-5) от «планка не найдена,
  отказ AC-3» сделано напрямую через `gitcmd.show`, а НЕ через
  established-узел `_read_branch_text_or_refuse` (тот же файл,
  `fsm.py:432-450`), который для ЭТОЙ ЖЕ операции — чтения артефакта с
  чужой/артефактной ветки — существует именно затем, чтобы отличить
  «файла на ветке нет легитимно» от «файл не прочитан из-за сбоя git»
  (докстринг `_read_branch_text_or_refuse` прямо ссылается на инцидент
  T030, журнал ~17:35 25.08.2026, «не молчаливый дефолт `schema_version 1
  без AC-разметки`»). В новом коде оба случая схлопнуты: `spec_text, _ =
  gitcmd.show(...)`; `meta = (yamlmini.frontmatter(spec_text) if
  spec_text is not None else None) or {}` — если `gitcmd.show` вернула
  `None` (ветка недоступна, транзиентный сбой git, гонка с материализацией
  и т.п.), `meta` становится `{}`, `guard.requires_ac_markup({})`
  возвращает `False` (дефолтный `schema_version` — 1), и функция уходит
  в `return "pulled"` — переход продолжается штатно, БЕЗ прогона
  приёмочной планки и БЕЗ единой записи в журнале о том, что чтение
  вообще не удалось. Это ровно тот «молчаливый зелёный проход», который
  SPEC «Критерии приёмки» AC-3/AC-4 прямо запрещают, — только для другого
  входного условия (сбой чтения, а не «ветка не несёт acceptance_tests/
  легитимно»), которое ACs SPEC не называют явно, но которое накрывает
  тот же принцип требования 5 («существующее поведение... не
  ослабляется») и напрямую конфликтует с прецедентом того же файла для
  того же класса операции.

  Воспроизвёл эмпирически (лёгкая FSM-песочница, `gitcmd.show`/
  `gitcmd.ls_tree_files` замокан на `(None, "git не ответил")`/`None`
  вместо легитимного «файла/ветки нет», остальное — как в
  `tests/test_branch_freshness_gate.py`): `fsm._pull_main_or_escalate`
  вернула `"pulled"`, журнал шагов задачи не получил ни одной записи о
  проблеме чтения (только `created: ...` от заведения задачи) — вызывающий
  код (`_cmd_approve`, `in_dev`, `_cmd_approve_merge_gate`,
  `_pass_acceptance_gate`) во всех четырёх местах трактует это как
  штатный «pulled» и продолжает переход/merge.

  Предложение: заменить прямой `gitcmd.show(artifact_branch_name, ...)`
  на `_read_branch_text_or_refuse(conn, task_id, artifact_branch_name,
  "SPEC.md")` (или эквивалентный явный разбор `reason` из `gitcmd.show`),
  чтобы сбой чтения давал СВОЙ именованный отказ (не эскалацию с
  текстом «приёмочные тесты красные», не тихий «pulled»), симметрично
  тому, что уже устроено для `spec_gate` (`fsm.py:786-791`).

- minor — `tests/test_branch_freshness_gate.py:340` (`test_approve_pulls_
  main_and_advances_when_acceptance_green`), `:474`
  (`test_advance_escalates_on_red_acceptance_after_pull_keeps_merge`),
  `:495` (`test_approve_escalates_on_red_acceptance_after_pull_keeps_
  merge`) — три изменённых этой веткой теста не несут докстринг «Ловит
  мутацию» (сам метод `write_acceptance_plank` докстринг несёt, но не
  тела тестов, которые реально стали чувствительны к новому источнику
  планки — без вызова `write_acceptance_plank()` они ушли бы по новой
  ветке AC-3/AC-5, а не по проверяемому сценарию). Не блокирует: сами
  критерии AC-1..AC-5 покрыты приёмочной планкой задачи
  (`tasks/01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests/
  test_ac1_ac2_pull_reads_plank_from_artifact_branch.py`,
  `test_ac3_ac4_ac5_missing_plank_named_refusal.py`) с корректными
  заявками «Ловит мутацию» — но тот же класс пробела в юнит-тестах уже
  отмечался ранее (`feedback_test_authoring_mutation_claim_gap`),
  повторяется третий раз подряд. Предложение: дописать по одной строке
  докстринга в каждый из трёх тестов на будущей итерации, не обязательно
  этой же.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm.py:344-347 (+ orchestrator/fsm.py:820-821, orchestrator/fsm_advance.py:763-764, orchestrator/fsm_merge_gate.py:326-327, orchestrator/canary.py:191-192) | сбой чтения SPEC.md с артефактной ветки (`gitcmd.show` вернула `None`) схлопывается в дефолтный `meta={}` → `requires_ac_markup` → `False` → `"pulled"`, вместо именованного отказа | переход/merge продолжается без прогона приёмочной планки и без диагностики при транзиентном сбое git на чтении артефактной ветки — тот самый «молчаливый зелёный проход», который AC-3/AC-4 запрещают для соседнего условия | использовать `_read_branch_text_or_refuse` (или эквивалентный явный разбор ошибки `gitcmd.show`) вместо прямого `gitcmd.show` + `or {}` |
| R1-F2 | open | tests/test_branch_freshness_gate.py:340,474,495 | три изменённых теста не обновили докстринг «Ловит мутацию» под новую чувствительность к источнику планки | придётся заново разбираться в намерении теста при следующей правке этого файла — не блокирует приёмку (см. «Замечания») | дописать докстринг с описанием мутации на следующей итерации |

## Вердикт

changes_requested — один blocker (R1-F1): узел, введённый ИМЕННО этой
задачей ради устранения «молчаливого зелёного прохода» (регрессия №12),
сам заводит новый вариант того же класса дефекта для случая сбоя чтения
SPEC.md с артефактной ветки, расходясь с уже существующим в этом же файле
прецедентом (`_read_branch_text_or_refuse`) для той же операции. Минорное
замечание R1-F2 можно закрыть в этой же итерации или отложить — не
блокирует.

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests -v` (планка задачи, материализована из головы `artifact/01m1r9yek08xeqwbfx0929wfvj` через `git show` по файлам, прогнана и удалена из рабочего дерева после — не закоммичена) — 10 тестов (AC-1..AC-8, AC-10, AC-11), все зелёные; AC-9 — manual (обоснованно: правка `.github/workflows/ci.yml` не исполнима в песочнице, GitHub Actions рантайм недоступен), AC-12 — skip (обоснованно: регрессия существующего набора уже покрыта штатным CI-джобом `python` на каждый пуш).
- `python3 -m unittest tests.test_branch_freshness_gate -v` — 12 тестов, все зелёные.
- `python3 -m unittest tests.test_fsm_autogate tests.test_artifact_materialization tests.test_merge_gate_ci_wait tests.test_fsm_merge_gate_done_snapshot -v` — 21 тест, все зелёные (модули, затронутые требованием 5/«Влияние на систему»).
- `python3 -m unittest tests.test_canary -v` — 36 тестов, все зелёные (зона расширения ANSWER-1).
- Эмпирическое воспроизведение R1-F1: отдельный скрипт вне REVIEW.md/tests (scratchpad), лёгкая FSM-песочница с `gitcmd.show`/`gitcmd.ls_tree_files`, замоканными на сбой (`(None, "git не ответил")`/`None`) вместо легитимного «файла/ветки нет» — `fsm._pull_main_or_escalate` вернула `"pulled"` без единой записи в журнале о сбое чтения.
- `python3 scripts/codebase_map.py` (регенерация вручную, изменения не оставлены в дереве) — расхождение с закоммиченной картой только в строке `built_at_sha` (не дефект, конвенция `docs/codebase-map.md` в скиле ревьювера).
- `git apply --check` диффа `.github/workflows/ci.yml`, приложенного к PLAN.md, — на detached worktree от актуального `main` (41ea4d4f) — применяется чисто.
- Сверил зоны: `orchestrator/canary.py`/`orchestrator/fsm_advance.py` действительно вне `zones:` SPEC.md (`orchestrator/fsm.py, orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_postmerge.py, .github/workflows/ci.yml`) — расширение легитимно по ANSWER-1.md.
- Полный набор `tests/` не прогонял (штатно гоняет CI на каждый пуш, решение Оператора 05.09 — см. скил ревьювера); диффа `tests/` на предмет ослабления ассертов не нашёл (все изменения — новый helper и добавленные проверки, ни одна существующая проверка не удалена и не смягчена).

## Предложения системе

- `feedback_test_authoring_mutation_claim_gap` (памятка) подтверждается
  третий раз подряд этой же задачей (R1-F2): юнит-тесты в `tests/`,
  модифицированные ради смены источника данных (не ради нового
  критерия), стабильно не получают обновлённую заявку «Ловит мутацию»,
  хотя приёмочные тесты той же задачи конвенцию соблюдают. Возможно,
  стоит явно указать в `skills/test-authoring.md`, что «изменённый»
  тест — это любое изменение тела/фикстуры, а не только новых
  assertions, а не оставлять это на усмотрение автора.
