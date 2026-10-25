---
task: 01M5T79C5GFJGQ9XCTH8W0PDFQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Скорость пульта, git 3: чтения git из клона и рабочей копии — через gitcmd

## Фаза A: план
- Таблица покрытия полна: требования 1–5 привязаны к шагам 1–2 и файлу сторожа от test_author.
- Шаги размера MR: три функции `gitcmd`, перевод семи мест, юнит-тесты, карта.
- Подход согласуется с архитектурой: одна точка запуска git в `gitcmd`, `carpentry` для места 1 не используется (требование 2). Подмены `acceptance.subprocess` из требования 4 в PLAN названы и прогнаны («Влияние на систему»).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | В пяти модулях прямых запусков git больше нет: сторож `ast` зелёный. `_launch`/`_run_capture` не используются. Импорт `subprocess` в `outcome_integrity.py` остался (нужен `tz_check`/`outcome_integrity` для `CompletedProcess`/подмены). В `reference_cache.py` убраны `subprocess`/`threading`: в `tests/` нет подмен `reference_cache.(subprocess|threading)` (проверил grep). |
| 2 | OK | `gitcmd.read` (срок, байтовый вход/выход, `Timeout` вместо `TimeoutExpired`), `read_env` (`Popen`, `-C`, `cwd=config.ROOT`, `pult_env(env)`, `kill`+`communicate` по сроку), `read_stream` (порции, предел, таймер с `kill`; `OverLimit`/`Timeout`/код возврата различимы, `LaunchFailed` при отказе запуска). `config` в `gitcmd` импортирован (`gitcmd.py:10`). |
| 3 | OK | Сверил старое и новое тело каждого места по diff. Аргументы, `-C`, окружение, сроки (15 / `CORE_REFERENCE_GIT_TIMEOUT_SEC` / остаток дедлайна; у мест 6–7 срока нет) прежние. `read` не передаёт незаданные ключевые аргументы. Тексты отказов совпадают: `"git не ответил (TimeoutExpired)"` равен прежнему `type(exc).__name__`. Порядок проверок места 4 прежний: предел → срок → код; `TimeoutExpired` конструктора даёт `SOURCE_FAILED` через `LaunchFailed`. `OSError` места 1 по-прежнему выходит исключением. |
| 4 | OK | Новые функции не зовут `git`/`in_repo`/`show`/`ls_tree_files`. Места 2,3,5,6,7 идут через `subprocess.run` того же модуля `subprocess`. Подмены `gitcmd.subprocess.run` в `tests/` патчат атрибут общего модуля, и путь им виден как раньше. Места 1 и 4 остались на `Popen`. Тесты с подменой `acceptance.subprocess` прогнаны (см. ниже). |
| 5 | OK | `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py` зелёный; `tests/test_invariants.py` не менялся. |

## Замечания
Блокеров и major нет.

- minor — `orchestrator/reference_cache.py` (`_list_tree`, после `except gitcmd.Timeout`) — проверка `time.monotonic() > deadline` в месте дублирует проверку `end` внутри `read_stream`. Поведение от этого прежнее, и проверку можно оставить как страховку от расхождения `end`/`deadline`. Последствий нет; это вкус, в реестр не заносится.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний уровня, требующего исправления, нет.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5T79C5GFJGQ9XCTH8W0PDFQ`: 94 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider` по файлам `tests/test_gitcmd_reads.py`, `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py` и файлам AC-3 (`test_01m4s24963r9h18an2xdp6r15b_cache.py`, `test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`, `test_outcome_gate_module.py`, `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py`), а также `test_tz_check.py`, `test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `test_report_outcome_module.py` (подмена `acceptance.subprocess`): 252 passed, 196 subtests passed.
- `git diff --stat 1f02aff4f -- tests/ docs/invariants.md` показывает только два новых файла (guard и `test_gitcmd_reads.py`). Существующие тесты не правлены, ослаблений нет.
- grep `tests/` на подмены `(gitcmd|brief|tz_check|reference_cache|outcome_integrity).(subprocess|threading)`. Подмен удалённых импортов `reference_cache` нет. Все подмены `gitcmd.subprocess.run` патчат общий модуль.
- Временная мутация: из `read_env` убран `process.kill()`. `tests/test_gitcmd_reads.py -k read_env` покраснел (`test_read_env_kills_and_drains_on_timeout` FAILED), затем `git checkout -- orchestrator/gitcmd.py`, рабочее дерево чистое.

## Предложения системе
