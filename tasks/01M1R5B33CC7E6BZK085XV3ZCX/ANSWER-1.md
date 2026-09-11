---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M1R5B33CC7E6BZK085XV3ZCX
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. AC-4: вариант (а), исполнено Оператором штатным каналом `amend-tests`
   (11.09, лок планки сдвинут a460ff4c -> 68171e0e): в `_sandbox.py`
   добавлен помощник `commit_minimal_plank(task_id)` (SPEC.md schema_version 2
   без skip_tests + одна зелёная проверка, коммит в артефактную ветку
   через `artifact_branch.commit_files`), вызовы — в `setUp` обоих классов
   `test_ac4_pull_main_or_escalate.py`. Прогон Оператора на твоём коде:
   3 из 3 зелёные.
2. AC-15: вариант (а), тем же `amend-tests`: первый assert после
   `cmd_advance` — состояние `verifying` (ADR-0015), затем перевод в
   `review` CAS-приёмом `store.set_state`, второй `cmd_advance` снят,
   перевод в `acceptance` ожидает `review`. Сценарий дошёл до самого
   мержа и нашёл скрытый дефект main, не твой: guard не знал
   `PASSPORT.md`, который пульт пишет для внешнего target. Исправлено
   hotfix №21 в main (коммит c52f54ba, `scripts/guard.py`).

Дальше: подтяни origin/main (`git merge origin/main` в worktree — там
hotfix №21 и мержи 11.09: approve без sha, самовыбор интерпретатора,
wait-zone; конфликты разрешай, сохраняя обе стороны), планку не трогай,
прогони её синхронно (17 из 17) и полный `tests/` по правилам скила,
PLAN.md — раздел «## Возврат — правка планки AC-4/AC-15 и hotfix №21»,
status: ready, коммит до конца хода. Бюджет поднят до $180,
израсходовано $127 — один ход.
