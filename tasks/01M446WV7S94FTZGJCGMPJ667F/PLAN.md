---
task: 01M446WV7S94FTZGJCGMPJ667F
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне

## Подход
- `workspace.ensure_clone`: после успешного `git clone`, хуков и
  идентичности — `artifact_branch.fetch_all_from_origin(clone)` (ленивый
  импорт: `artifact_branch` импортирует `workspace`). Узел тот же, что у
  `docs --fetch-all`: fetch в приватное пространство и сдвиг локальной
  ссылки только вперёд. Неудача — одна строка с причиной в stdout, исход
  `ensure_clone` остаётся успешным. Ветка «каталог уже есть» не меняется.
- Возврат из verifying (CI красный на 3516dc44,
  `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest::
  test_pull_freshness_fetches_inside_the_target_clone_not_the_pult`):
  причина — `cmd_init` песочницы заводит клон `acme` заглушкой git, у
  которой `clone` отвечает rc=0, но каталога не создаёт; `_fetch_docs_refs`
  делал `git -C <клон> fetch ... refs/artifacts/*` в несуществующий
  каталог, и тест брал его как `fetch_calls[0]`. Правка без правки теста:
  `_fetch_docs_refs` (`orchestrator/workspace.py`) не зовёт fetch, если
  после успешного `git clone` каталога клона нет, — fetch'у некуда класть
  ссылки (настоящий git в таком случае тоже отказал бы); причина —
  одной строкой с подсказкой `docs --fetch-all`, исход `ensure_clone` не
  меняется. Сторож — `tests/test_workspace_clone_docs_refs.py`.
- `check_artifact_ref_sync`: закрытая задача без локальной ссылки, у
  которой ссылка в origin = коммиту закрытия, не даёт проблемы, а
  считается; при ненулевом счёте к результату добавляется одна строка
  `ok` с числом и подсказкой `artel.py docs --fetch-all` — и рядом с
  `warn`, и рядом с `skip`, и рядом с итоговой `ok`.
- `_fix_unsent_closed_refs`: порядок решений по закрытой задаче —
  origin = коммиту закрытия → ничего; объект коммита закрытия в клоне
  есть → прежнее правило (голова = коммиту закрытия → `artifact_branch.push`;
  голова другая → не досылать; локальной ссылки нет → push sha из клона
  без force); объекта в клоне нет → у задачи артели ищется в git главной
  копии (`config.ROOT`) и досылается оттуда `git push <url origin клона>
  <sha>:refs/artifacts/<id>` без force; отказ — строка `[FIX]` с id и
  stderr; объекта нет нигде (или задача внешнего проекта) — строка `[FIX]`
  с id и коммитом закрытия.
- `cmd_doctor(fix=True)`: `_fix_project_clones` переносится в начало
  блока `--fix`, до `_fix_unsent_closed_refs`; оба по-прежнему до
  `all_checks`.

## Шаги
1. Код: `orchestrator/workspace.py`, `orchestrator/doctor/artifact_branches.py`,
   `orchestrator/doctor/cli.py`; регенерация `docs/codebase-map.md`.
2. Тесты: `tests/test_doctor_closed_ref_fix.py` — AC-6 (досылка из главной
   копии и отказ непродвигающего push), AC-7 (объекта нигде нет), AC-8
   (порядок починок в `cmd_doctor`). AC-1…AC-5 покрыты долгоживущим
   `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`.
3. Прогон: планка `plank-run`, затронутые модули tests/ (doctor,
   artifact_ref_sync, workspace, multitarget), guard на PLAN.md.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3 (AC-1…AC-3 — долгоживущий файл) |
| 2 | 1, 3 (AC-4, AC-5 — долгоживущий файл) |
| 3 | 1, 2 |
| 4 | 1, 2 |
| 5 | 2 |

## Влияние на систему
- `ensure_clone` на заведении клона делает ещё один fetch: новые ссылки
  только добавляются/сдвигаются вперёд, перезаписи нет; отказ fetch не
  отказывает в заведении — поведение `init`/`new`/`doctor --fix` прежнее
  за вычетом строки причины.
- Досылка из главной копии — только `push` без force в origin клона;
  git главной копии не меняется (push по адресу не пишет ссылок
  отслеживания). Гейты, тесты и инварианты не ослабляются; проверка
  `artifact-ref-sync` перестаёт предупреждать только в случае, где
  origin уже несёт коммит закрытия, — настоящие расхождения остаются `warn`.
- Откат — revert merge-коммита задачи.

## Проверка (итог шага)
- `artel.py plank-run 01M446WV7S94FTZGJCGMPJ667F` — 5 passed.
- `tests/test_doctor_closed_ref_fix.py`, долгоживущий
  `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py`,
  `test_artifact_ref_sync`, `test_doctor_artifact_branch_sync`,
  `test_workspace`, `test_doctor`, `test_git_hooks`, `test_multitarget`,
  `test_01m42pencs26d0656x8fr7dfa7_project_area`,
  `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo`,
  `test_docs_fetch_edges`, `test_01m41vtse5n15p5p2wzf4gf2bq_docs_command`,
  `test_codebase_map` — 331 passed.
- Мутации сторожей проверены временно: досылка с `+<sha>:<ref>`, поиск в
  главной копии без условия «артель», `_fix_project_clones` в конце
  блока `--fix`, отказ от поиска в главной копии и молчание при
  отсутствии объекта — каждый из пяти тестов краснел на своей мутации,
  код возвращён.
- Карта `docs/codebase-map.md` регенерирована.
- Итерация после возврата из verifying: `tests/test_branch_freshness_gate.py`
  + `tests/test_workspace_clone_docs_refs.py` — 14 passed; мутация
  (условие каталога клона снято) красит оба — и новый сторож, и
  `TargetSourcedRemoteTest`; код возвращён. Планка — 5 passed.
  Полный набор в шаге запрещён конвенцией (решение Оператора 05.09) —
  вместо него все 87 модулей `tests/`, задевающих `cmd_init`/`cmd_new`/
  `ensure_clone`/`cmd_doctor`/`artifact_ref_sync`, тремя пачками:
  609 passed; 867 passed; 420 passed / 16 failed — все 16 в
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` с отказом «artel.py
  approve/pin-update: команда недоступна процессу роли developer»
  (тест зовёт CLI пульта под окружением шага роли), к правке не
  относятся; в CI окружения роли нет.

## Риски
- Песочницы тестов, где клон артели — ссылка на корень: клон «уже есть»,
  fetch не идёт — их поведение не меняется.

## Предложения системе
- `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest` берёт
  `fetch_calls[0]` из всех вызовов git с `cmd_init` — любой новый fetch
  на заведении клона ломает его без изменения поведения сверки свежести;
  надёжнее отбирать вызовы, сделанные только внутри `cmd_advance`.
- `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` красный в шаге роли
  (CLI пульта отказывает процессу роли) — его нельзя прогнать в шаге,
  хотя возврат требует «полный прогон tests/».
