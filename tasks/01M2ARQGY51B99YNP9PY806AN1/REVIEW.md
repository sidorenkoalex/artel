---
task: 01M2ARQGY51B99YNP9PY806AN1
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гонка на FETCH_HEAD — приватная ссылка fetch в трёх местах

## Фаза A: гейт плана

1. **Покрытие требований SPEC шагами плана** — полное. Все три требования
   SPEC (примитив без FETCH_HEAD / перевод трёх мест / отсутствие литерала
   FETCH_HEAD в вызовах) закрыты шагами 1–3, 6 таблицей «Покрытие
   требований» PLAN.md — таблица соответствует фактическому diff.
2. **Размер шагов** — PLAN бьёт работу на 7 шагов размера ревьюируемого MR
   (новый примитив, три перевода, правка тестовой инфраструктуры, новый
   тестовый файл, откат дублирующей правки защищённого пути) — не
   микрооперации и не «сделать всё».
3. **Подход vs конвенции/архитектура** — подход (`git fetch
   +refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid>` → `rev-parse --verify`
   → `update-ref -d` в `finally`) — прямая реализация SPEC AC-1/AC-2 без
   отклонений; сигнатуры трёх переводимых функций сохранены (AC-4), `repo`
   диспетчеризуется по образцу существующего `in_repo` (тот же паттерн
   `in_repo(repo, *args) if repo else git(*args)`, что и у остальных
   примитивов `gitcmd.py`). Конфликта с архитектурой не вижу.

Отдельно проверил разрешение эпизода с защищённым путём
`tests/test_invariants.py` (PLAN, «Подход», абзацы 3–4): файл действительно
в `config.PROTECTED_PATHS` (orchestrator/config.py:540); диф ветки к
`a2e2324a` по этому файлу пуст (`git log --oneline a2e2324a..HEAD --
tests/test_invariants.py` — ничего), фикс `failing()` под
`refs/artel/fetch/*` в файле присутствует и пришёл подтяжкой main
(коммит Оператора `a2e2324a`) — легитимный путь, прямой правки
защищённого пути в диффе ветки нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. Примитив `gitcmd.py` без FETCH_HEAD | OK | `gitcmd.fetch_ref_sha` (gitcmd.py:414–463): fetch в приватную ссылку, `rev-parse --verify`, `update-ref -d` в `finally` — AC-1/AC-2/AC-3 подтверждены исполнением (см. «Проверено исполнением»). |
| 2. Три места переведены, имена/сигнатуры прежние | OK | `gitcmd.fetch_head_sha` — тонкая обёртка (`return fetch_ref_sha(remote, ref)`); `fsm._origin_main_sha(target_name, *, repo=None)` и `fsm_merge_gate._origin_main_sha(ctx)` — сигнатуры byte-identical прежним, реально исполняют `fetch_ref_sha` (подтверждено `OriginMainShaRealGitWiringTest`, реальный git). Потребители `fetch_head_sha` (`workspace.py`, `artifact_branch.py:145`) не тронуты, AC-4. |
| 3. Литерал `FETCH_HEAD` вне докстрингов отсутствует | OK | `grep -n FETCH_HEAD` по трём файлам зоны — все вхождения внутри докстрингов (gitcmd.py:420,422,469,470; fsm.py:117,119; fsm_merge_gate.py:90,91), ни одного в аргументах вызова git. Подтверждено `test_ac5_no_fetch_head_literal.py` (зелёный). |

## Замечания

Пусто — блокеров и major не найдено. Реализация точно следует SPEC/PLAN;
приватная ссылка действительно устраняет гонку на общем `FETCH_HEAD`
(проверено воспроизведением сценария гонки — см. ниже), уборка ссылки
через `try/finally` корректна на всех путях выхода, `repo`-диспетчеризация
не даёт трафику примитива утечь в `config.ROOT` при работе с клоном
target'а.

Единственное отличие от прежнего поведения, не описанное явно в PLAN: два
из трёх переведённых мест (`fsm._origin_main_sha`, `fsm_merge_gate.
_origin_main_sha`) раньше звали `git fetch -q ...`, новый общий примитив
`fetch_ref_sha` флаг `-q` не передаёт — `git fetch` в новой реализации
пишет пару строк прогресса в stderr вместо тихого завершения. Не поднимаю
как замечание: результат fetch (stdout/stderr) на успешном пути нигде не
читается и не логируется (`fetch.returncode` — единственное, что
проверяется), наблюдаемого поведения для вызывающего кода это не меняет,
сценария поломки не вижу.

## Реестр замечаний

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M2ARQGY51B99YNP9PY806AN1/acceptance_tests -p "test_*.py"` — 9/9 зелёных (все AC-1–AC-9 задачи, включая AC-7 — воспроизведение гонки на FETCH_HEAD с подставленным чужим sha между fetch и чтением, не просочилось в результат).
- `python3 -m unittest tests.test_gitcmd_fetch_ref_sha` — 6/6 зелёных (новый модуль; реальный git, включая репро гонки, `repo`-провод в отдельный клон, отказ недоступного remote, первый реальный git-прогон `fsm._origin_main_sha`/`fsm_merge_gate._origin_main_sha`).
- `python3 -m unittest tests.test_branch_freshness_gate tests.test_invariants tests.test_pull` — 84/84 зелёных (в т.ч. `MergeOnlyFromMergeGateTest` из `test_invariants.py` — заглушка `failing()` под `refs/artel/fetch/*` работает; `TargetSourcedRemoteTest` — переписанный assert по подстроке рефспека проходит).
- `python3 -m unittest tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_merge_gate_scratch_worktree_cleanup tests.test_merge_gate_ci_wait tests.test_gitcmd_branch_reads tests.test_gitcmd_check_ignore tests.test_workspace tests.test_amend` — 115/115 зелёных.
- `python3 -m unittest tests.test_gitcmd_carpentry tests.test_capacity_gate tests.test_protected_paths_gate tests.test_ci_status_kind_gate tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note` — 39/39 зелёных.
- `python3 -m unittest tests.test_doctor tests.test_kill_cleanup tests.test_timeout_checkpoint tests.test_doctor_artifact_branch_sync tests.test_doctor_artifact_branch_ci tests.test_notes` — 228/228 зелёных (потребители `fake_git`/`SpyRun`, переведённых на `refs/artel/fetch/*`).
- `python3 scripts/codebase_map.py` (регенерация в рабочей копии, сравнение с закоммитированной версией `git diff -- docs/codebase-map.md`, затем `git checkout -- docs/codebase-map.md`) — расхождение только в строке `built_at_sha`, содержимое карты свежее и совпадает с фактическим состоянием зоны задачи.
- `grep -n FETCH_HEAD orchestrator/gitcmd.py orchestrator/fsm.py orchestrator/fsm_merge_gate.py` — все вхождения только в докстрингах (AC-5 вручную, дополнительно к зелёному `test_ac5_no_fetch_head_literal.py`).
- `git log --oneline a2e2324a..HEAD -- tests/test_invariants.py` — пусто; защищённый путь в диффе ветки не звучит, фикс пришёл легитимной подтяжкой main.

Полный набор `tests/` не прогонялся (гоняется CI на каждый пуш; CI коммита
7aedaa3c зелёный, 14 проверок, см. пакет) — прогнаны модули, затронутые
диффом, плюс основные потребители тестовой инфраструктуры (`fake_git`/
`SpyRun`), итого ~481 тест, все зелёные.

## Предложения системе

Пусто.
