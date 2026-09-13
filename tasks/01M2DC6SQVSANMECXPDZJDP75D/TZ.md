---
task: 01M2DC6SQVSANMECXPDZJDP75D
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рефакторинг R8: общая песочница тестов — базовые классы вместо копий setUp и подмножеств PATCHED_ATTRS

Источник: отчёт ревизии №6 docs/audits/code-revision-2026-09-13.md, находка
CR-2026-09-13-5 ★ и ТЗ-черновик Р-5; роадмап §3 фаза R, пункт R8.
Предусловия выполнены 13.09: фикс утечки тестов (01M2CN465W) и Р-1…Р-4
(01M2CN3VV9, 01M2CN3ZCS, 01M2CN42RV, 01M2CYQR03) смержены; тихое окно,
параллельных задач нет.

Факты:
- tests/sandbox.py — 966 строк, 7 классов, `ALL_CONFIG_ATTRS` :63–64;
  собственные подмножества `PATCHED_ATTRS` в 10 файлах; 270 `setUp`,
  17–26 групп одинаковых тел (tests/test_agent_log.py:84 =
  tests/test_step_cost.py:73 = tests/test_agent_failure.py:47;
  tests/test_mutation_claim_gate.py:24 = tests/test_protected_paths_gate.py:87);
  побайтно совпадают помощники `event`, `fake_git_config`; `result_event`
  (x3), `spec_text`, `assistant_event` — разные сигнатуры, НЕ дубли.
- tests/test_invariants.py — защищённый путь (группы :439/733 и :635/1420
  не трогать); `tasks/*/acceptance_tests/_sandbox.py` (93 файла) — вне
  задачи.

Требуется (поведение не меняется):
1. Побайтно одинаковые `setUp` и помощники — в базовые классы
   tests/sandbox.py; файлы переходят на наследование.
2. Подмножества `PATCHED_ATTRS`: обоснованные остаются с комментарием
   «почему подмножество», необоснованные — `TmpRootTest` целиком.
3. Ассерты и сценарии не меняются; полный набор зелёный; прогон
   не создаёт каталогов в `.artel/worktrees` (критерий фикса сохраняется).
4. PLAN: таблица переносов, откат revert'ом одного merge.

Зоны: tests/.

Приложением: tests/test_invariants.py (защищённый путь — не правится);
skills/test-authoring.md (шаблон будущих планок — вне задачи).

Не входит: test_invariants.py; исторические `_sandbox.py` планок;
дедупликация помощников с разными сигнатурами.

Рамка: $25.
