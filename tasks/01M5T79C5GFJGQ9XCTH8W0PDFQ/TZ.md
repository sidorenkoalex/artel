---
task: 01M5T79C5GFJGQ9XCTH8W0PDFQ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Скорость пульта, git 3: чтения git из клона и рабочей копии — через gitcmd

# Скорость пульта, git 3: чтения git из клона проекта и рабочей копии — через orchestrator/gitcmd.py

## Факты

Очередь скорости, решение Оператора 24.10.2026 («задачи по git 1, 5, 2, 3, 4 — по очереди между волнами»); git 1, 5, 2 смержены. git 3 — условие для git 4 (память чтений git в контексте команды пульта, ~12–16 % вызовов): память можно повесить только на одну точку запуска git, а часть чтений идёт мимо `orchestrator/gitcmd.py` прямым `subprocess`. Сама git 3 скорости почти не даёт.

Чтения git мимо `gitcmd` (сверка 25.10, пин 7e0c636c):
1. `orchestrator/acceptance.py:2944` — `suite_tree_hash`, вложенная `git()`: `read-tree`/`add -u`/`rm --cached`/`write-tree` через `Popen` + `communicate(timeout=15)`, `GIT_INDEX_FILE`.
2. `orchestrator/brief.py:552` — `_clone_git` (`ls-tree -z`, `show`), вывод байтами, `timeout`.
3. `orchestrator/reference_cache.py:299` — `branch_commit` (`rev-parse --verify`), `timeout`.
4. `orchestrator/reference_cache.py:352` — `_list_tree` (`ls-tree -r -l -z`), потоковое чтение `Popen` с пределом байт и остановкой по сроку.
5. `orchestrator/reference_cache.py:410` — `_cat_blobs` (`cat-file --batch`, вход байтами), `timeout`.
6. `orchestrator/tz_check.py:151` — `_git`/`_git_ok` (`ls-tree`, `show`, `grep`, `rev-parse`), вывод байтами.
7. `orchestrator/advance_gates/outcome_integrity.py:581` — `_added_lines` (`diff … -U0`), вывод байтами.

`gitcmd` уже даёт `git`, `in_repo`, `carpentry` (своё окружение, вход, байтовый вывод), `pult_env`; не даёт срока (`timeout`, `TimeoutExpired`) и потокового чтения с пределом.

## Требуется

1. Семь мест выше запускают git через функции `orchestrator/gitcmd.py`; прямого `subprocess` с git в этих модулях не остаётся.
2. В `gitcmd` — то, чего не хватает этим местам, с сохранением их поведения: срок выполнения с прежними значениями и прежней обработкой истечения (именованный отказ, не исключение наружу); потоковое чтение с пределом байт и остановкой по сроку для `_list_tree` (или `_list_tree` остаётся потоковым через новую функцию `gitcmd` — выбор за аналитиком); байтовый вывод и вход; своё окружение (`GIT_INDEX_FILE`) — через `carpentry` или равноценную функцию.
3. Поведение семи мест не меняется: те же аргументы git, тот же репозиторий (`-C <клон>` или рабочая копия), то же окружение (маркер `pult_env`), те же коды отказа и тексты причин, то же число процессов git (тесты считают процессы шпионом `Popen`).
4. Перенос не должен попадать под подмены `gitcmd.git` в тестах, которые подменяют её заглушкой на любую команду (`tests/sandbox.py:2173` и ~59 файлов `mock.patch.object(gitcmd, "git", fake_git)`): перенесённые чтения идут через функцию `gitcmd`, которую эти заглушки не подменяют, или аналитик доказывает по коду, что ни один такой тест не исполняет перенесённое место. Тихое изменение поведения существующих тестов — дефект.
5. Новый тест-сторож: в модулях `acceptance.py`, `brief.py`, `reference_cache.py`, `tz_check.py`, `advance_gates/outcome_integrity.py` нет прямого запуска git через `subprocess` (по образцу `tests/test_invariants.py:1879` `CarpentryGitCallsGoThroughGitcmdTest`, но отдельным долгоживущим файлом задачи, не правкой `tests/test_invariants.py`).

Критерии приёмки:
- в пяти модулях нет `subprocess.run`/`Popen` с git; сторож красный при возврате любого из семи мест на прямой `subprocess`;
- существующие тесты этих мест зелёные без правки: `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py` (в том числе `:296`, `:323`, `:334`, `:510`, `:971`), `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py` (`:236`, `:538`, `:554`), `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py:547`, `tests/test_outcome_gate_module.py:2525`, `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py:208`;
- истечение срока в `gitcmd` у каждого места даёт прежний именованный отказ (тест на каждое место);
- полный набор `tests/` зелёный.

Зоны: `orchestrator/gitcmd.py`, `orchestrator/acceptance.py`, `orchestrator/brief.py`, `orchestrator/reference_cache.py`, `orchestrator/tz_check.py`, `orchestrator/advance_gates/outcome_integrity.py`, `tests/` (долгоживущие файлы задачи).

Только чтение: `tests/sandbox.py`, `tests/test_invariants.py`, `docs/invariants.md`, `orchestrator/config.py`.

Существующие тесты: правка любого существующего теста — эскалация до SPEC с перечнем тестов и предлагаемой правкой; мандат — только Оператор.

Не входит: `orchestrator/checkpoint.py:1941` `_main_copy_status` (намеренно вне `gitcmd.git`: не должен попадать в сверяемую тестами последовательность вызовов шага); клоны канарейки `orchestrator/canary.py:1189–1208`; `orchestrator/stack.py:383`, `:611` и `orchestrator/agent_log.py:48` (проверки версии и корня главной копии); `orchestrator/plank_helper.py` (копируется в планку как `_pult.py`, по контракту не импортирует `orchestrator`); `orchestrator/doctor/project_checks.py:448`; `gitcmd.check_ignore`; `scripts/` (отдельные процессы); память чтений (задача git 4).

Рамка: $40. Набор моделей — по умолчанию.
