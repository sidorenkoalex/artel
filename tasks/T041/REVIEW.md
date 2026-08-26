---
task: T041
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Протокол рестарта после таймаута шага: WIP-чекпоинт оркестратора

## Фаза A — план

Покрытие требований в PLAN.md полное (таблица «Покрытие требований»
закрывает все 7 требований SPEC), шаги — проверяемые единицы (функция +
переименование + тесты + документация), подход не конфликтует с
существующей архитектурой фиксации (`fixation.fix`/`_fix_dogfood`/
`_fix_external`, `store.set_state`). Замечание по плану — в разделе
«Замечания» ниже (пункт про `store.task_target`): PLAN нигде не
рассматривает внешние target'ы, хотя `commit_timeout_checkpoint`
физически обходит именно тот диспетчер (`fixation.fix(task_id, target)`),
которым живёт остальная фиксация.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | Частично | Чекпоинт коммитится, но только для догфуда (см. замечание major ниже) — `commit_timeout_checkpoint` не читает `store.task_target`, всегда бьёт по `config.ROOT` через `gitcmd.git`. |
| 2 | OK | Сообщение коммита дословно `f"{task_id}: WIP-чекпоинт после таймаута шага {role}"`, подтверждено `test_ac1_...` (сверка `git log -1 --format=%s`). |
| 3 | OK | `store.journal(conn, task_id, "orchestrator", "WIP-чекпоинт после таймаута шага", detail)` — actor и пометка таймаута в action, подтверждено `test_ac1_...`. |
| 4 | OK | Вызов `commit_timeout_checkpoint` только внутри `if timed_out:` (orchestrator/runner.py:544-552), ветка `if rc != 0:` (строка 554) не тронута; `test_ac3_...` проверяет explicit. |
| 5 | OK | `fixation.check_integrity`/`fix`/`read` не изменены (diff не затрагивает `orchestrator/fixation.py`); `test_refixation_keeps_check_integrity_clean_after_the_commit` подтверждает поведение. |
| 6 | OK | Ветка `timed_out` в `cmd_run`/`run_agent_once` по-прежнему возвращает `"timeout"` без ретрая; не менялась, кроме добавленного вызова чекпоинта. |
| 7 | OK | Все операции — `gitcmd.git("add"/"diff"/"commit")`, `gitcmd.head_sha()`; прямого `subprocess`/`git` в обход модуля нет. |

## Замечания

- **blocker** — `docs/codebase-map.md` — карта устарела относительно
  фактического дерева коммита `f2a8fba`: перегенерировал `scripts/
  codebase_map.py` локально на HEAD этой ветки и получил реальную (не
  только `built_at_sha`) разницу — отсутствует целая секция `##
  tests/test_timeout_checkpoint.py` и этот файл не добавлен в списки
  «Импортируется» у `orchestrator/fixation.py`, `orchestrator/gitcmd.py`,
  `orchestrator/runner.py`, `orchestrator/store.py`. Похоже, карта была
  regenerated ДО того, как в этот же коммит добавили `tests/
  test_timeout_checkpoint.py` (94 строки, тот же `f2a8fba`), и повторно
  не перегенерирована. CI-джоб `codebase-map` (`.github/workflows/
  ci.yml:54-81`) гоняет ровно ту же регенерацию и диффит без строки
  `built_at_sha` — на этой ветке он покраснеет (проверено воспроизведением
  локально). Это тот самый класс дефекта, который описан в conventions-core
  и уже случался на T028/T029. Исправление: `python3 scripts/
  codebase_map.py` ещё раз на актуальном дереве и закоммитить результат.

- **major** — `orchestrator/runner.py:343-396` (`commit_timeout_checkpoint`),
  строки 378/381 (`gitcmd.git("add", "-A")` / `gitcmd.git("diff",
  "--cached", "--quiet")`) — функция коммитит только рабочее дерево
  пульта (`gitcmd.git` всегда работает с `cwd=config.ROOT`,
  `orchestrator/gitcmd.py:16`), не сверяясь с `store.task_target(conn,
  task_id)`. Вся остальная фиксация в проекте таргет-осведомлённая:
  `fixation.fix(task_id, target)` (fixation.py:49-53) диспетчерит
  `_fix_dogfood` vs `_fix_external(target)` (последняя коммитит через
  `gitcmd.in_repo(config.PROJECTS / target, ...)`, fixation.py:90-114), и
  `role_cwd(target)` (runner.py:322-338) для внешнего target отдаёт
  `.artel/projects/<target>/workspace/`, а не `config.ROOT`. Сценарий
  поломки: при таймауте шага задачи с `target != config.DEFAULT_TARGET`
  (`role_cwd` = внешний workspace, где реально работал агент)
  `commit_timeout_checkpoint` вместо этого дерева закоммитит текущее
  состояние `config.ROOT` (репозиторий пульта) — либо тихо ничего не
  сделает (если ROOT в этот момент чист), оставив реальный WIP внешнего
  target'а незакоммиченным (AC-1 не выполняется для этой задачи), либо, что
  хуже, закоммитит в ROOT постороннее незакоммиченное состояние пульта под
  сообщением о совсем другой задаче/ветке. Сейчас это не воспроизводимо
  «живьём» — `targets.yaml` объявляет единственный target `artel`
  (`config.DEFAULT_TARGET`, ADR-0003 3д: «Догфуд — особый случай до A7»),
  поэтому `store.task_target` всегда возвращает догфуд и путь не
  задет. Но PLAN нигде не фиксирует это как сознательно принятую границу
  задачи (ни в «Не входит» SPEC, ни в «Риски»/«Влияние на систему» PLAN —
  там разбирается только edge-case «роль ещё не создала ветку», без
  упоминания target'а вовсе), а SPEC требование 1 говорит просто
  «рабочее дерево ветки задачи» без ограничения догфудом. Пока
  многотаргетность не активирована — не блокер, но нужно явно
  зафиксировать это ограничение (SPEC «Не входит» или PLAN «Риски»),
  либо сделать `commit_timeout_checkpoint` таргет-осведомлённой той же
  диспетчеризацией, что уже есть в `fixation.fix`/`role_cwd`.

- **minor** — `tests/test_timeout_checkpoint.py` — юнит-тесты покрывают
  отказ только на шаге `git add` (`test_git_add_failure_commits_nothing_
  and_journals_nothing`); отказ `git diff --cached --quiet` (код возврата
  вне {0,1}) и отказ `git commit` (строки 381 и 388-391
  `orchestrator/runner.py`) не покрыты отдельными тестами, хотя PLAN
  («Риски»/шаг 5) обещал проверить «отказ на любом из трёх шагов». Не
  блокирует — логика симметрична уже протестированному пути и повторяет
  устоявшийся паттерн `fixation._fix_external`, но при желании закрыть
  класс целиком двумя дополнительными кейсами.

## Вердикт

`changes_requested`:
1. (blocker) Перегенерировать `docs/codebase-map.md` на актуальном
   дереве и закоммитить — иначе CI-джоб `codebase-map` красный.
2. (major) Явно зафиксировать в SPEC «Не входит» или PLAN «Риски»
   ограничение чекпоинта догфудом (`config.DEFAULT_TARGET`) — либо
   сделать `commit_timeout_checkpoint` таргет-осведомлённой, как
   `fixation.fix`/`role_cwd`.
3. (minor, по желанию) Добавить юнит-тесты на отказ `git diff`/`git
   commit` внутри `commit_timeout_checkpoint`, не только `git add`.
