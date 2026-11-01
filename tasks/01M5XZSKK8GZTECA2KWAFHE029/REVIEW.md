---
task: 01M5XZSKK8GZTECA2KWAFHE029
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab В1.1 — источник полного набора `full_suite: local | ci | both` на приёмке

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–5 → шаги 1–5; шаги размера MR.
- Подход согласован с ТЗ по направлению импорта: `targets` не импортирует
  `forge`, реестр подаётся атрибутом `targets.hosting_registry` из `ci.py`
  (`orchestrator/ci.py:28`). Проверено: `import orchestrator.forge`
  транзитивно грузит `ci`, так что в любом процессе с `forge` реестр
  выставлен; без `forge` проверка при загрузке пропускается, а хостинг без
  `job_test_report` ловится при использовании (`forge._call` → «не
  реализовано» → «неизвестно», `tests/test_ci_job_full_suite.py`) — это
  ANSWER-1 п. 2, риск честно назван в PLAN «Риски».
- «Влияние на систему» = diff: `fsm.py`, `fsm_merge_gate.py`, `forge.py`,
  `gitlab_adapter.py` не тронуты; существующие тесты `tests/` не менялись
  (`git diff --stat 309c4dc39...HEAD -- tests/` — только три новых файла,
  только добавления).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py:113-128,1079-1104,1332-1338`: `full_suite` точным значением из перечня (`None`/`CI`/`both-ci` — отказ), `ci_job` ровно при `ci`/`both` (умолчание `local` тоже запрещает), `report` обязателен, реестр без литерала; каждый отказ называет поле. Профиль — `project_profile.py:127-128,455-456` через общий `_with_component_fields`. |
| 2 | OK | `acceptance.py` `_ci_job_run`: три условия вынесены в `_ci_result_conditions` с `base` записи проекта; невыполненное — `FULL_SUITE_NOT_STARTED` + `UNKNOWN_PREFIX` + запись журнала с причиной; `fresh` в `ci` читает `forge` заново без локального прогона. `ci.job_full_suite`: последняя попытка по наибольшему `id`, право падать → «неизвестно», перечитывание номера попытки (ANSWER-1 п. 3), статус не `success`/`failed` → «неизвестно», отчёт `None`/пуст/чужой исход → «неизвестно» (ANSWER-1 п. 1), `failed`/`error` в отчёте при `success`/`failed` → красный, `failed` без падений → «неизвестно». Запись «полный набор: итог задания CI <job>, задание <id>, sha <sha>, тестов <n>» — дословно. `checks_local` — прежним путём в `acceptance_suite` после итога. |
| 3 | OK | `_ci_job_suite_run`: локальный прогон всегда, зелёный только при обоих зелёных; старший незелёный по общему `_NOT_GREEN_ORDER`, при равенстве — CI (пара «локальный красный + CI неизвестно» → «неизвестно»). Деталь называет оба источника (ANSWER-1 п. 6). |
| 4 | OK | `fsm_autogate.py:426` → `acceptance.is_ci_result`: подстрока артели либо деталь, начинающаяся `CI_JOB_RECORD`; у `both` деталь начинается записью CI. |
| 5 | OK | Путь артели/`local`: тексты причин, порядок проверок и `origin/main` прежние (сравнил удалённый и новый код построчно); `components_full_suite` — тот же порядок через `_not_green_rank`. Профиль `None` (артель) → `getattr(..., FULL_SUITE_LOCAL)`. |

## Замечания
Нет замечаний blocker/major/minor.

Проверенные сценарии поломки, которые не подтвердились:
- `full_suite: null` с `ci_job` — мог бы загрузиться и молча идти локально; нет: `_component_value_error` отдаёт отказ на `None` (не входит в перечень).
- `both`: локальный `NO_TESTS`/`TIMEOUT` при CI «неизвестно» — решает CI (ранг 0), «неизвестно» не теряется; локальный зелёный при CI красном — красный CI.
- `ComponentsPending` в начале `_acceptance_suite_run` перехвачен, отказ поднимается прежним `_task_own_profile` — поведение отказа прежнее.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py` — 13 passed.
- `python3 -m pytest -q -p no:cacheprovider tests/test_ci_job_full_suite.py tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py` — 42 passed.
- `artel.py plank-run 01M5XZSKK8GZTECA2KWAFHE029` — отказ «планки нет» (в refs/artifacts нет test_*.py): задача держится долгоживущими файлами, pytest не запускался.
- Временная мутация `orchestrator/ci.py` (`if result.status != "success"` → `if False` — `failed` без падений читается зелёным) — `-k ac8` долгоживущего файла: красный `test_ac8…[failed_clean]`, 1 failed / 10 passed; код возвращён `git checkout -- orchestrator/ci.py`, `git status` чист.
- Импорт: `python3 -c "from orchestrator import targets"` — `hosting_registry` = `None`, `ci` не загружен; после `from orchestrator import forge` — `ci` загружен (реестр выставлен).
- `python3 scripts/codebase_map.py` — diff карты без `built_at_sha` пуст (карта свежа); карта возвращена `git checkout`.

## Предложения системе
- Регистрация реестра хостингов побочным эффектом импорта `ci.py` (`targets.hosting_registry`) — временный обход запрета правки `forge.py`; в задаче, где `forge.py` в зоне, перенести строку туда (PLAN предлагает то же).
