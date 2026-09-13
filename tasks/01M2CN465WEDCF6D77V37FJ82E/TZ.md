---
task: 01M2CN465WEDCF6D77V37FJ82E
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

Источник: отчёт ревизии №5 docs/audits/code-revision-2026-09-12.md, находка
CR-2026-09-12-1 ★ (подтверждена ревизией №6: утечка повторилась в двух
полных прогонах, 54 каталога за прогон). Решение Оператора 13.09: волна
рефакторинга; это задача-фикс (не рефакторинг), предусловие для R8.

Факты:
- Полный прогон `tests/` из чистой копии создаёт 54 каталога в
  `.artel/worktrees` того корня, откуда импортирован пакет (38 из них —
  tests/test_timeout_checkpoint.py); в главной копии пульта накопилось
  243 сиротских каталога (97 МБ) при 16 зарегистрированных worktree.
- Механизм: `workspace.path` строит путь от `config.WORKTREES`
  (orchestrator/workspace.py:21–23), вычисленного при импорте
  (orchestrator/config.py:59); патч `config.ROOT` его не двигает.
  `tests/test_git_fixation.py:159` — класс `_GitFixationTmpRootTest` с
  собственным `PATCHED_ATTRS` без `WORKTREES` — регрессия коммита d692f2a6
  (список T045 заменён наследованием); `RealPultGitTest`
  (test_git_fixation.py:724) делает настоящий `git worktree add`.
  Другие подмножества `PATCHED_ATTRS`: tests/test_multitarget.py:104
  (`workspace.ensure` подменён — не течёт), tests/test_doctor.py:2413
  (намеренно) — сверить, не оставляют ли они `WORKTREES`/`BACKUP_MARKER`
  на настоящем корне.
- Ревизия №5 видела также перезапись отслеживаемого docs/codebase-map.md
  полным прогоном; ревизия №6 (два прогона) — нет. Проверить, есть ли
  тест, регенерирующий карту на настоящем `config.ROOT`, и при наличии
  завернуть в песочницу.

Требуется:
1. `PATCHED_ATTRS` в tests/test_git_fixation.py:159 включает `WORKTREES`
   (и всё, что `TmpRootTest.PATCHED_ATTRS` в tests/sandbox.py подменяет
   для путей на диске); остальные подмножества сверены — ни один класс не
   оставляет `config.WORKTREES` / `BACKUP_MARKER` на настоящем корне.
2. Критерий: полный прогон `tests/` из чистой копии (интерпретатор
   `.artel/venv`, `-n 4`) не создаёт ни одного каталога в
   `.artel/worktrees` и оставляет `git status --porcelain` пустым
   (замер до: 54 каталога).
3. Инвариант «после прогона — чисто» в tests/test_invariants.py —
   ТОЛЬКО приложением unified diff к PLAN.md (защищённый путь, коммитит
   Оператор); в ветке задачи файл не править.
4. Ассерты существующих тестов не меняются.

Зоны: tests/.

Приложением: orchestrator/workspace.py:21–23, orchestrator/config.py:59
(механизм — не правятся); tests/test_invariants.py (защищённый путь —
диффом в PLAN).

Не входит: правка workspace.py/config.py; перенос общих песочниц (R8 —
следующая задача); уборка 243 накопившихся каталогов в главной копии
(операторская уборка).

Рамка: $15.
