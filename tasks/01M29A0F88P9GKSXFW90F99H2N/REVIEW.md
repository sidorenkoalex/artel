---
task: 01M29A0F88P9GKSXFW90F99H2N
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: гейт заявки мутации — новые и изменённые тесты в tests/ без «Ловит мутацию» отклоняются на выходе in_dev, а не кругом ревью

## Служебное примечание к пакету ревью

Пакет снова заявил «SPEC.md/PLAN.md не найдены» и инкрементальный diff
«изменений нет» (диапазон в заголовке пакета: `e30fcd5d...HEAD`, а
`e30fcd5d` — это и есть текущий HEAD ветки, см. `git log --oneline -5`:
он сам, слитый merge-коммит «подтяжка main», лежит первым). Тот же
класс, что REVIEW.md итераций 2 и 3 уже отметило в «Предложения
системе» — повторяю замечание туда третий раз явно ниже.

Проверено напрямую по git-истории кодовой ветки (не по пакету):
- SPEC.md/PLAN.md/REVIEW.md/ANSWER-1.md присутствуют на диске рабочего
  каталога и прочитаны оттуда.
- `git log --oneline -3` ветки: `e30fcd5d` (merge «подтяжка main») ←
  `47b1f541` («01M29A0F88P9GKSXFW90F99H2N: закрыт R1-F2 — третья
  причина сбоя gitcmd.show различается через ls_tree_files») ←
  `8be42ff5` (чужой коммит другой задачи, слитый до этого). Фактический
  код изменения этой итерации — коммит `47b1f541`
  (`git show --stat 47b1f541`): `orchestrator/fsm_advance.py` (+30/-10),
  `tests/test_mutation_claim_gate.py` (+49), `docs/codebase-map.md`
  (регенерация). Ревью сделано по этому коммиту и по коду HEAD
  (идентичен, `47b1f541` — предок `e30fcd5d` без дальнейших правок
  зоны в merge).

## Фаза A: гейт плана

PLAN.md несёт раздел «Итерация 4 — закрытие R1-F2 (ANSWER-1.md)»,
описывающий именно то решение, которое реализовано в `47b1f541`:
третья причина `head_source is None` различается через
`gitcmd.ls_tree_files(branch, "tests")`, а не по тексту причины
`gitcmd.show`. Подход соответствует решению Оператора (ANSWER-1.md) и
предложению ревьювера итерации 3 (R1-F2). Шаги и покрытие требований —
без изменений с итерации 1, замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (guard.py: `MUTATION_CLAIM` + `test_functions_without_mutation_claim`, AC-1..AC-4) | OK | Не менялось с итерации 2. `python3 -m pytest tests/test_guard_mutation_claim.py -q` — зелёный (см. «Проверено исполнением»). |
| 2 (fsm_advance.py: `_mutation_claim_gate`, порядок вызова, fail-closed на сбое git, AC-5/AC-7) | OK | Ранее «реализовано не так» (R1-F2, needs_work итерация 3) — теперь закрыто. `orchestrator/fsm_advance.py:1002-1038`: третья причина `gitcmd.show` (любой сбой на пути, реально присутствующем в дереве HEAD) теперь отказывает независимо от текста причины через `path in gitcmd.ls_tree_files(branch, "tests")`; путь отсутствует в дереве — легитимное удаление, пропуск; `ls_tree_files` сам вернул `None` — permissive-фоллбэк на прежнее текстовое сравнение (двойной сбой git, дальше не сужается — есть отдельный fail-closed рубеж на сбой `diff_base`/`diff_names` выше). Порядок вызова (`_zones_gate_refuses` → `_mutation_claim_gate` → `_review_rework_gate_refuses`, `orchestrator/fsm_advance.py:1414-1419`) подтверждён, не изменился слиянием main. |
| 3 (пропуск для канарейки/внешнего target, AC-8) | OK | Не менялось, `orchestrator/fsm_advance.py:974`. |
| 4 (отказ доходит до `advance_refusal_history` без правки runner.py/brief.py, AC-9) | OK | Не менялось. |

## Замечания

(нет открытых замечаний.)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F2 | accepted | orchestrator/fsm_advance.py:1002-1038 | fail-closed на сбой `gitcmd.show` был закрыт только для 2 из 3 причин `head_source is None`; третья причина (любой иной сбой `git show` на пути, реально существующем в HEAD) трактовалась как легитимное удаление и пропускалась | новый/изменённый тест без заявки мутации мог проскочить гейт при нестандартном сбое `git show` на существующем файле | Разработчик реализовал предложенный итерацией 3 вариант через `gitcmd.ls_tree_files(branch, "tests")` (коммит `47b1f541`): `path in tree` (tree не `None`) → отказ независимо от текста причины; путь отсутствует в `tree` → легитимное удаление; `tree is None` (git не ответил и на эту проверку) → permissive-фоллбэк на прежнее текстовое сравнение. Проверено: (а) новые тесты `test_unclassified_show_failure_on_path_present_in_tree_refuses` и `test_unclassified_show_failure_on_path_absent_from_tree_skips` в `tests/test_mutation_claim_gate.py` покрывают обе новые ветки, докстринги несут «Ловит мутацию: …» с содержательным текстом сценария; (б) залоченный `test_ac5_file_deleted_in_head_is_skipped` не задет — прогнан, зелёный; (в) `path in tree` корректен по формату: `gitcmd.git()` вызывается с `cwd=config.ROOT` (`orchestrator/gitcmd.py:16`), поэтому `ls_tree_files` возвращает repo-root-относительные пути вида `tests/test_x.py`, тот же формат, что и `diff_names`/`path` в цикле гейта — сравнение строк совпадает без несоответствия префиксов. Замечание закрыто, перевожу в `accepted`. |

## Вердикт

approved — все четыре требования SPEC реализованы и подтверждены,
единственное открытое замечание (R1-F2) закрыто по предложенному в
итерации 3 варианту и не конфликтует с залоченными приёмочными
тестами.

## Проверено исполнением

- `git log --oneline -5` (кодовая ветка) — подтверждён фактический
  коммит изменения итерации 4 (`47b1f541`) и его положение относительно
  HEAD (`e30fcd5d`, merge без дальнейших правок зоны).
- `git show --stat 47b1f541` и `git show 47b1f541 -- orchestrator/fsm_advance.py tests/test_mutation_claim_gate.py` — подтверждено содержимое правки, изменения строго в зоне задачи (`scripts/guard.py, orchestrator/fsm_advance.py, tests/`) + регенерация `docs/codebase-map.md`.
- `python3 -m pytest tests/test_guard_mutation_claim.py tests/test_mutation_claim_gate.py -q` — 26 passed.
- `python3 -m pytest tasks/01M29A0F88P9GKSXFW90F99H2N/acceptance_tests/ -q` — 21 passed (включая залоченный `test_ac5_file_deleted_in_head_is_skipped`, не задетый правкой).
- `python3 -m pytest tests/test_zones_gate.py tests/test_capacity_gate.py tests/test_fsm_advance_gate_smoke.py tests/test_advance_guard.py tests/test_guard_schema.py -q` — 97 passed, 21 subtests passed (существующие гейты не задеты).
- `python3 scripts/codebase_map.py --check` — чисто, карта свежая.
- Чтение `orchestrator/fsm_advance.py:958-1042` (`_mutation_claim_gate`, актуальная версия), `orchestrator/gitcmd.py:9-19` (`git`, cwd=config.ROOT), `orchestrator/gitcmd.py:368-389` (`show`), `orchestrator/gitcmd.py:438-449` (`ls_tree_files`) — подтверждена корректность сравнения путей и полнота закрытия трёх причин сбоя.
- `git log --oneline -- orchestrator/fsm_advance.py:1414-1419` (чтение самого файла) — порядок вызова гейтов не изменился слиянием main.
- Полный набор `tests/` не прогонялся (решение Оператора 05.09 — гоняет CI на каждый пуш; CI коммита `e30fcd5d` зелёный, 14 проверок, см. заголовок пакета).

## Предложения системе

- Третий раз подряд для ОДНОЙ И ТОЙ ЖЕ задачи сборка ревью-пакета не
  находит настоящий диапазон коммитов вердикта и отдаёт «SPEC.md/PLAN.md
  не найдены» + пустой diff, когда sha предыдущего вердикта совпадает с
  текущим HEAD ветки (после подтяжки main тем же коммитом, что и
  вердикт). Уже отмечено в REVIEW.md итераций 2 и 3 — повторяю ещё раз,
  чтобы наблюдение не потерялось: стоит искать диапазон по git-истории
  самого REVIEW.md в артефактной ветке, а не полагаться на переданный
  извне sha.
