---
task: 01M2CN465WEDCF6D77V37FJ82E
type: spec
author_role: analyst
status: ready        # draft | ready | approved
schema_version: 5
zones: tests/.
budget_usd: 25
---

# SPEC: Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

## Контекст

Полный прогон `tests/` из чистой копии пульта создаёт каталоги в
`.artel/worktrees` того корня, откуда импортирован пакет: 54 каталога за
прогон (38 из них — из `tests/test_timeout_checkpoint.py`), в главной
копии пульта накопилось 243 сиротских каталога (97 МБ) при 16
зарегистрированных worktree. Находка подтверждена дважды — ревизией №5
(docs/audits/code-revision-2026-09-12.md, CR-2026-09-12-1 ★) и ревизией
№6 (docs/audits/code-revision-2026-09-13.md) на двух полных прогонах.

Механизм: `workspace.path` (orchestrator/workspace.py:21–23) строит путь
от `config.WORKTREES`, вычисленного один раз при импорте
(orchestrator/config.py:59); подмена `config.ROOT` в тесте его не
двигает — нужна отдельная подмена `config.WORKTREES`. Класс
`_GitFixationTmpRootTest` (tests/test_git_fixation.py:159) задаёт
собственный `PATCHED_ATTRS` без `WORKTREES` и без `BACKUP_MARKER` — оба
входят в полный список подменяемых путей `TmpRootTest.PATCHED_ATTRS` =
`ALL_CONFIG_ATTRS` (tests/sandbox.py:62–65), унаследованный по умолчанию
до регрессии коммита d692f2a6 (список T045 заменён явным подмножеством).
Тесты этого файла (в частности `RealPultGitTest`, tests/test_git_fixation.py:724)
делают настоящий `git worktree add` и, без подмены `WORKTREES`, пишут в
`.artel/worktrees` реального корня.

## Требования

1. `_GitFixationTmpRootTest.PATCHED_ATTRS` (tests/test_git_fixation.py:159)
   включает `WORKTREES` и `BACKUP_MARKER` — оба сегодня отсутствуют в
   списке этого класса.
2. Прочие классы в `tests/`, задающие собственный `PATCHED_ATTRS`
   (в частности `tests/test_multitarget.py:104`, `tests/test_doctor.py:2413`,
   и любой другой класс с собственным подмножеством), сверены: ни один не
   оставляет `config.WORKTREES`/`config.BACKUP_MARKER` незапатченными в
   ситуации, где код этого класса реально дотягивается до записи по этим
   путям на настоящем корне пульта. Найденная утечка чинится тем же
   способом (расширение `PATCHED_ATTRS` этого класса), в рамках зоны
   `tests/.`.
3. Полный прогон `tests/` из чистой копии (интерпретатор `.artel/venv`,
   `pytest -n 4`) не создаёт ни одного каталога в `.artel/worktrees` и
   оставляет `git status --porcelain` пустым (замер до фикса: 54
   каталога за прогон).
4. Новый инвариант «после прогона тестов — рабочее дерево чисто»
   (docs/invariants.md, tests/test_invariants.py) вносится ТОЛЬКО
   приложением unified diff к `PLAN.md` — тот же приём, что и для
   защищённых путей (skills/conventions-core.md: `git apply --check` на
   чистом дереве перед сдачей); сам `tests/test_invariants.py` в
   коде ветки задачи не редактируется, файл коммитит Оператор.
5. Ассерты существующих тестов не меняются.

## Критерии приёмки

AC-1. `tests/test_git_fixation.py:159` — `_GitFixationTmpRootTest.PATCHED_ATTRS`
содержит `WORKTREES` и `BACKUP_MARKER`.

AC-2. Ни один класс в `tests/`, задающий собственный `PATCHED_ATTRS`
(кроме `_GitFixationTmpRootTest`, покрытого AC-1), не оставляет
`config.WORKTREES`/`config.BACKUP_MARKER` незапатченными в ситуации, где
код этого класса реально пишет по этим путям на настоящий корень
(класс, где сам механизм записи подменён отдельно — например,
`workspace.ensure` целиком заменён моком, как в `tests/test_multitarget.py:104`
— утечкой не считается).

AC-3. Полный прогон `tests/` из чистой копии (интерпретатор
`.artel/venv`, `pytest -n 4`) не создаёт ни одного каталога в
`.artel/worktrees` и оставляет `git status --porcelain` пустым.

AC-4. Диф кода ветки задачи не содержит правок `tests/test_invariants.py`;
новый инвариант «после прогона — чисто» приложен к `PLAN.md` отдельным
unified diff по этому файлу, который проходит `git apply --check` на
чистом дереве `main`.

AC-5. Ассерты существующих тестов (кроме диффа AC-4, который не входит
в код ветки задачи) не изменены.

## Не входит

- правка `orchestrator/workspace.py` / `orchestrator/config.py` —
  механизм (вычисление `config.WORKTREES` при импорте, построение пути в
  `workspace.path`) не трогаем;
- перенос общих песочниц в единый модуль (R8 — следующая задача волны
  рефакторинга);
- уборка 243 уже накопившихся сиротских каталогов в главной копии
  пульта (операторская уборка, не код задачи);
- прямая правка `tests/test_invariants.py` в ветке задачи — только
  приложением unified diff к `PLAN.md` (см. AC-4).

## Материалы

- docs/audits/code-revision-2026-09-12.md — находка CR-2026-09-12-1 ★.
- docs/audits/code-revision-2026-09-13.md — ревизия №6, подтверждение
  повторной утечки на двух прогонах.
