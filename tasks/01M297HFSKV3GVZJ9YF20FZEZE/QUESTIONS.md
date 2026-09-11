---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: база ветки задачи — origin/main, а не локальный пин

## Вопросы

1. **Требование 1 просит `workspace.ensure` при отсутствии ветки задачи
   заводить её «для внешнего target — от базы target по `targets.yaml`,
   тем же источником, что `fsm._origin_main_source`». Но по всей
   кодовой базе `workspace.ensure`/worktree `config.ROOT` явно
   документированы как self-специфичный механизм, не работающий с
   внешними target:**
   - `orchestrator/pull.py::evaluate` докстринг: «отдельный worktree
     (`workspace.ensure`, self-специфичный механизм) не заводится и не
     нужен» для target ≠ self — сравнение/merge для внешнего target
     идут прямо в его клоне `.artel/projects/<target>/workspace`
     (`repo_context.py`), не в worktree `config.ROOT`.
   - `orchestrator/runner.py::role_cwd` вызывает `workspace.ensure`
     ТОЛЬКО когда `target == config.DEFAULT_TARGET`; для любого другого
     target берёт `role_cwd_path` (каталог `.artel/projects/<target>/
     workspace`), путь `workspace.ensure` не пересекает вовсе.
   - `orchestrator/catalog.py::cmd_new` докстринг: код/ветку задачи для
     ЛЮБОГО target, включая артель, заводит роль-разработчик — для
     артели «в `config.ROOT` напрямую», для внешнего — «в клоне
     целевого»; `cmd_new` сама ветку не создаёт.
   - Буквальный импорт `fsm._origin_main_source` из `workspace.py`
     завёл бы цикл `fsm → pull → checkpoint → workspace → fsm` (`fsm.py`
     импортирует `pull._merge_conflict_note`, `pull.py` импортирует и
     `checkpoint`, и сам `workspace`; `checkpoint.py` тоже импортирует
     `workspace`) — `pull.py` уже явно обходит этот цикл инъекцией
     параметром, а не импортом, ровно по этой причине (её же докстринг).

   Варианты:
   - **A) Только self/артель.** `workspace.ensure` меняет базу НОВОЙ
     ветки на `origin/<MAIN_BRANCH>` артели (`_origin_main_source`
     самой функции не касается — self-case там литерал `("origin",
     config.MAIN_BRANCH)`); фраза ТЗ про «внешний target» — про
     принцип источника на будущее, не про новую способность сейчас.
     Сигнатура `workspace.ensure(task_id, branch)` не меняется, зоны —
     как заявлено в ТЗ (`orchestrator/workspace.py`, `orchestrator/
     doctor/`, `orchestrator/catalog.py`, `tests/`), рамка `$35`
     реалистична.
   - **B) Полная поддержка внешних target.** `workspace.ensure` (или
     новый узел рядом) получает параметр `target`/`RepoContext`, все 4
     вызывающих места (`runner.py`, `orchestrator/pull.py`, `orchestrator/
     amend.py`, `orchestrator/canary.py`) прокидывают его; способ обхода
     цикла импорта (инъекция параметром по образцу `pull.py`, либо
     дублирование функции по образцу `fsm_merge_gate._origin_main_sha`)
     — решает разработчик. Зоны и `budget_usd` в SPEC придётся расширить
     за пределы заявленных в ТЗ (эти 4 файла + возможный `repo_context.py`),
     рамка `$35` из ТЗ, скорее всего, недостаточна — потребуется либо
     повышение рамки Оператором, либо деление задачи.

   Дефолт при молчании: **A** — совпадает с действующей архитектурой
   (`workspace.ensure` нигде не вызывается для внешнего target),
   укладывается в заявленные зоны и рамку `$35`, не создаёт цикл
   импорта.

## Контекст

- Прочитан `orchestrator/workspace.py` (текущий `ensure`: `git worktree
  add -b branch wt_path config.MAIN_BRANCH`, без обращения к target).
- Прочитаны `orchestrator/fsm.py:70-153` (`_origin_main_source`/
  `_origin_main_sha`), `orchestrator/pull.py:268-305` (`evaluate`,
  self-специфичность `workspace.ensure` явно в докстринге), `orchestrator/
  runner.py:630-680` (`role_cwd` — ветвление по target ДО обращения к
  `workspace.ensure`), `orchestrator/repo_context.py` (механизм внешнего
  target — отдельный клон, не worktree `config.ROOT`), `orchestrator/
  catalog.py:162-222` (`cmd_new` не создаёт кодовую ветку ни для какого
  target), `orchestrator/doctor/root_pin.py` (существующая соседняя
  проверка `root-pin`, другая семантика/направление сравнения, для
  ориентира по требованиям 2-3).
- Требования 2 и 3 ТЗ (проверка `doctor`/`new`) однозначны: «главная
  копия» — одна, это `config.ROOT`, per-target ветвления там нет; SPEC по
  ним можно писать без уточнений, они не входят в блокер.

## Блокирует

Не могу разметить AC-1/AC-2 (требование 1: база новой ветки задачи от
origin) без выбора между A и B — от этого зависят зоны, `budget_usd` и
сама формулировка критерия (только self или self+внешний target).
SPEC.md не пишу до ответа.
