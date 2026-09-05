---
task: 01M1RNZ6V7TTTTYAHBMF8JBQQS
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: регрессия №14 — приёмка гоняет планку на коде кодовой ветки, а не на коде пульта

Примечание к пакету ревью: инкрементальный diff пакета (78551cc7..HEAD)
снова указывал не на тот коммит — тот же класс проблемы, что уже
отмечен в «Предложениях системе» итерации 1 и итерации 2 (третий
воспроизводимый случай для этой же задачи). `78551cc7` — не коммит
вердикта итерации 2 (тот писался на `ff0e3209`/артефактной ветке над
кодовым состоянием `c6192f53`), а более поздний коммит РАЗРАБОТЧИКА
(«подтяжка main», уже после ответа на итерацию 2). Из-за этого пакет
показал только `docs/backlog.md` (+1 строка) вместо всего diff с
закрытием R2-F1/R2-F2 и мержем hotfix 86673499 (ANSWER-3). Пересобрал
реальный diff вручную: `git diff c6192f53..da458c28` (`c6192f53` —
кодовое состояние, на котором фактически писался REVIEW.md итерации 2:
`a6595d19` с сообщением «закрытие REVIEW итерации 2» — прямой потомок
`c6192f53`). Ревью ниже — по этому реальному diff (6 файлов: `canary/
guids.txt`, `canary/pool.sealed`, `docs/backlog.md`, `docs/codebase-
map.md` — всё это принесено подтяжкой main, не авторская правка этой
задачи; `orchestrator/fsm_advance.py`, `tests/test_acceptance.py` —
авторская правка).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (материализация планки в рабочий каталог кода, оверлей поверх устаревшей копии) | OK | не изменилось с итерации 2, подтверждено повторно — `orchestrator/fsm.py:337-339` (`_pull_main_or_escalate`) после разрешения конфликта ANSWER-3 побайтово совпадает с состоянием ДО слияния hotfix 86673499 (`git diff c6192f53..da458c28 -- orchestrator/fsm.py` — пусто) |
| 2 (`code_root` прогона = рабочий каталог кода) | OK | `orchestrator/acceptance.py:19-57` не тронут этим инкрементом, поведение прежнее |
| 3/5 (общий вход материализации/прогона, без дублей) | OK | hotfix 86673499 предлагал параллельную ветку логики (`artifact_branch.materialize_task_dir` + temp-каталог + `shutil.rmtree` для self-target); при разрешении конфликта она отброшена целиком в пользу уже реализованного этой задачей узла — `grep -n "artifact_branch\|shutil\|tempfile" orchestrator/fsm.py` не находит ничего в `_pull_main_or_escalate` |
| 4 (отказ называет каталог и cwd одной строкой) | OK | не изменилось |
| R2-F1 (мёртвый `import shutil`) | Исправлено, подтверждено | `orchestrator/fsm_advance.py:8` — строка убрана; `grep -c shutil orchestrator/fsm_advance.py` → 0 |
| R2-F2 (фикс R1-F1 без персистентного теста) | Исправлено, подтверждено | `tests/test_acceptance.py:77-109` — `MaterializeFromBranchGitFailureTest::test_none_from_ls_tree_files_leaves_existing_plank_untouched`, докстринг класса ссылается на R2-F2/REVIEW итерации 2, докстринг метода несёт корректную заявку «Ловит мутацию»: `ls_tree_files` замокан на `None`, ожидается, что существующий файл планки НЕ стирается. Проверено чтением `orchestrator/acceptance.py:101-103` (`if paths is None: return tdir` до построения `wanted`/прунинга) — мутация «вернуть `or []`» действительно ломает именно этот тест (прунинг стёр бы `existing`), заявка докстринга правдоподобна |

ANSWER-3 (влить main, разрешить конфликт в `fsm.py` в пользу SPEC, не
дублируя hotfix) выполнен корректно: единственный содержательный
конфликт — `orchestrator/fsm.py::_pull_main_or_escalate`, разрешён в
пользу ветки HEAD целиком, что подтверждается нулевым diff этого файла
между состоянием до и после слияния. Из main взято только
непересекающееся (`canary/guids.txt`, `canary/pool.sealed`, снятая
строка и новая запись `docs/backlog.md`, перегенерация `docs/codebase-
map.md` — только `built_at_sha`, не признак дефекта).

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:101-103 | `ls_tree_files(...) or []` терял различие None/[] | транзиентный сбой git стирал реальную планку | закрыто и принято в итерации 2, изменений с тех пор не было — сохранено |
| R1-F2 | accepted | tests/test_branch_freshness_gate.py, tests/test_fsm_map_conflict_autoresolve.py | новые assert'ы без докстринга «Ловит мутацию» | конвенция test-authoring не соблюдена | закрыто и принято в итерации 2, изменений с тех пор не было — сохранено |
| R2-F1 | accepted | orchestrator/fsm_advance.py:8 | мёртвый `import shutil`, оставшийся после удаления `shutil.rmtree` этой же задачей | не ломает поведение, засоряет код | строка импорта убрана (`a6595d19`), `grep -c shutil` → 0, подтверждено |
| R2-F2 | accepted | orchestrator/acceptance.py:101-103 (фикс R1-F1) | фикс не был покрыт персистентным unit-тестом | будущий рефакторинг/мерж-конфликт мог незаметно вернуть `or []` | добавлен `tests/test_acceptance.py::MaterializeFromBranchGitFailureTest` (`a6595d19`), мутация проверена чтением и логически воспроизводима — подтверждено |

Реестр закрыт целиком (все записи `accepted`) — гейт `review ->
verifying` не заблокирован.

## Вердикт

approved

## Проверено исполнением

- Восстановлен реальный diff инкремента: `git diff c6192f53..da458c28`
  (пакет ошибочно показал diff от `78551cc7`, коммита разработчика, а
  не коммита, на котором писался REVIEW.md итерации 2) —
  `--stat`: `canary/guids.txt`, `canary/pool.sealed`, `docs/backlog.md`,
  `docs/codebase-map.md`, `orchestrator/fsm_advance.py`,
  `tests/test_acceptance.py`.
- `git diff c6192f53..da458c28 -- orchestrator/fsm.py` — пусто:
  подтверждает, что разрешение конфликта ANSWER-3 (hotfix 86673499)
  сохранило поведение этой ветки без дублирования логики hotfix.
- `python3 -m unittest tests.test_branch_freshness_gate
  tests.test_fsm_map_conflict_autoresolve tests.test_acceptance
  tests.test_fsm_autogate tests.test_artifact_materialization -v` —
  33 теста (включая новый `MaterializeFromBranchGitFailureTest`), `Ran
  33 tests ... OK`.
- `python3 -m unittest tests.test_amend tests.test_dry_run
  tests.test_multitarget tests.test_multitarget_invariants
  tests.test_canary` — `Ran 135 tests ... OK`.
- `python3 -m unittest tests.test_zones_gate tests.test_capacity_gate
  tests.test_advance_guard tests.test_review_registry_gate
  tests.test_merge_gate_ci_wait tests.test_verifying_ceiling
  tests.test_fsm_draft_mr_reentry` — `Ran 56 tests ... OK`.
- `python3 -m unittest discover -s
  tasks/01M1RNZ6V7TTTTYAHBMF8JBQQS/acceptance_tests -v` — `Ran 11
  tests ... OK` (AC-1..AC-9, включая намеренно-красные под-сценарии
  AC-6/AC-7, красные по замыслу фикстуры внутри теста, не по сбою).
- `grep -n "code_root\|materialize_from_branch\|shutil\|tempfile"
  orchestrator/fsm_advance.py orchestrator/acceptance.py` и
  аналогичный grep по `orchestrator/fsm.py` — один вход материализации
  (`acceptance.materialize_from_branch`) и один вход прогона
  (`acceptance.run(..., code_root=...)`) на всех трёх точках, `shutil`/
  `tempfile` не осталось.
- `git diff c6192f53..da458c28 -- docs/codebase-map.md | grep -v
  built_at_sha` — меняется только заголовок с `built_at_sha`, не
  признак дефекта.
- Чтением: `tests/test_acceptance.py:77-109` (новый тест и его
  докстринг), `orchestrator/acceptance.py:60-124`
  (`materialize_from_branch` целиком), `orchestrator/fsm.py:300-374`
  (`_pull_main_or_escalate`), `orchestrator/fsm_advance.py:220-335`
  (`review`/`verifying`).
- Полный набор `tests/` в шаге не гонял (решение Оператора 05.09) — его
  гоняет CI на каждый пуш; сверка «набор не ослаблен» сделана по diff
  `tests/` инкремента (только добавление теста в `test_acceptance.py`,
  никаких удалённых/изменённых ассертов).

## Предложения системе

- Инкрементальный diff ревью-пакета для этой задачи ошибся с sha
  «предыдущего вердикта» ТРЕТИЙ раз подряд (итерация 1 — SPEC/PLAN не
  найдены; итерация 2 — sha `cde22926` вместо коммита вердикта
  итерации 1; итерация 3 — sha `78551cc7`, коммит разработчика после
  ответа на итерацию 2, вместо `c6192f53`/`a6595d19`, где реально
  писался и закрывался REVIEW.md итерации 2). Корневая причина уже
  найдена и задокументирована по соседней задаче
  (01M1R9YEK08XEQWBFX0929WFVJ, REVIEW.md итерация 5):
  `orchestrator/role_prompt.py:106` зовёт `review.review_package(...,
  t["branch"], ...)` КОДОВОЙ веткой, `orchestrator/review.py:214`
  читает SPEC.md/PLAN.md/diff-базу именно этим параметром — для задач
  post-T094 (артефакты только на артефактной ветке) это структурно не
  может работать. Стоит завести/поднять приоритет фикса
  (`artifact_source.resolve(conn, task_id)` вместо `t["branch"]`), а не
  продолжать разбирать это вручную в каждой задаче по третьему разу.
