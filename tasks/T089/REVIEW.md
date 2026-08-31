---
task: T089
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2
---

# REVIEW: Тестовые хелперы третьего поколения — в sandbox

## Фаза A: проверка плана
PLAN.md покрывает все пять требований SPEC таблицей соответствия;
шаги 1–6 — проверяемые единицы (по группе файлов на приём хелпера),
не микрооперации и не «сделать всё разом». Разведка PLAN (grep по
сигнатурам + `git branch` для списка живых задач) подтверждена
independently (см. ниже) и совпадает с фактическим diff. Подход не
конфликтует с существующей архитектурой `tests/sandbox.py` (T037) —
хелперы добавлены рядом с уже существующими `TmpRootTest`/`fake_git`/
`FakeProc`, стиль модуля выдержан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все пять хелперов (`_ts_ago`, `FakeStream`, `SpyRun`, `RealGitSandbox`, `_dead_pid`) определены в `tests/sandbox.py`; см. замечание minor ниже про один пропущенный дубль вне списка. |
| 2 | OK | `tests/test_release.py`, `test_merge_lock.py`, `test_lease.py`, `test_parallel_limit.py`, `test_doctor.py`, `test_agent_log.py`, `test_step_cost.py`, `test_agent_failure.py`, `test_invariants.py`, `test_auto_cycle.py`, `test_gitcmd_branch_reads.py`, `test_answer_branch_reads.py` — локальных определений не осталось, все импортируют из `tests.sandbox`. |
| 3 | OK | Открытые задачи (T085–T090) не содержат копий хелперов в `acceptance_tests/` — действие не требовалось, подтверждено собственным grep (см. «Проверено исполнением»). |
| 4 | OK | Известный остаток (13 файлов, 4 хелпера) перечислен в PLAN.md; список воспроизведён независимым прогоном `_repo_scan.py` — совпадает 1:1. Ни один файл остатка не входит в diff. |
| 5 | OK | `git diff --stat main...HEAD` — только `tests/*.py`, `tests/sandbox.py` и `tasks/T089/*` (SPEC/PLAN/TZ/acceptance_tests); `orchestrator/`, `scripts/` не тронуты. |

## Замечания

- minor — `tests/test_agent_log.py:38` / `tests/test_step_cost.py:34` (функция
  `event(**fields)`, 3 строки, byte-identical в обоих файлах: `return
  json.dumps(fields, ensure_ascii=False) + "\n"`) — PLAN утверждает
  «Других дублей того же класса тем же способом (grep по определению
  класса/функции верхнего уровня без отступа) в `tests/*.py` не
  нашлось», но именно этим способом (`^def \w+` верхнего уровня, тот же
  метод, что описан в PLAN) находится ещё один byte-identical дубль —
  `event()`. Формально подпадает под требование 1 SPEC («то же имя/
  назначение хелпера, скопированное в несколько файлов»). Не блокирую:
  риск расхождения тут не тот, что у `_ts_ago` (нет общего формата,
  который могло бы «развезти» — это тривиальный джейсон-враппер), и
  SPEC делает включение таких находок дискреционным («если по ходу
  правки обнаруживаются»), а не обязательным для всех классов дублей
  без разбора. Предложение: либо свести и `event()` заодно (три
  строки, дёшево), либо явно отметить как сознательно оставленный вне
  рамки — на усмотрение разработчика, не требую отдельной итерации
  ради этого одного замечания.

## Вердикт
approved

Единственное замечание — minor, не блокирует и не откладывает мерж;
оставляю на усмотрение разработчика (можно закрыть попутно следующей
задачей или отдельным малым коммитом, без новой итерации ревью).

## Проверено исполнением
- `python3 -m unittest discover -s tests` — 1099 тестов, все зелёные (AC-6).
- `python3 -m unittest discover -s tasks/T089/acceptance_tests -p 'test_*.py' -v`
  — 7 тестов (AC-1..AC-5, покрывающих оба ассерта каждого), все зелёные.
- `python3 scripts/guard.py --all` — «GUARD: ок (295 файлов)».
- `grep -rn "^def _ts_ago\|^class FakeStream\|^class SpyRun\|^class RealGitSandbox\|^def _dead_pid" tests/ orchestrator/ scripts/`
  — только пять определений, все в `tests/sandbox.py` (AC-1/AC-2).
- `git branch --format='%(refname:short)'` — живые локальные ветки
  `task/t0{85..90}-...` (плюс T001) совпадают со списком «открытых
  задач» из PLAN.md; `acceptance_tests/` этих задач не содержит копий
  хелперов (проверено `_repo_scan.py` напрямую в интерпретаторе) —
  AC-3 подтверждён «зелён с рождения».
- Независимый прогон `_repo_scan.py` (вычисление remainder для
  закрытых задач) — 13 файлов/хелперов, список совпадает 1:1 со
  «Известным остатком» PLAN.md; `git diff --name-only main...HEAD` не
  содержит ни одного из этих 13 файлов (AC-4).
- `git diff --stat main...HEAD -- . ':!tests' ':!tasks/*/acceptance_tests'`
  — только `tasks/T089/{PLAN,SPEC,TZ}.md` вне исключённых путей;
  боевой код (`orchestrator/`, `scripts/`) не затронут (AC-5).
- Прослежена цепочка `test_auto_cycle.py::SpyRun` → `gitcmd.subprocess.run`
  → `gitcmd.branch_exists` (`rev-parse --verify refs/heads/*`): в
  `orchestrator/auto.py` нет прямых/косвенных вызовов `branch_exists`
  (только `catalog.py`/`cleanup.py`/`doctor.py`/`workspace.py`, ни один
  не задействован в auto-цикле) — риск, отмеченный самим PLAN
  («Риски»), подтверждён безвредным, не просто продекларирован.
- Точечное чтение (не из пакета): `orchestrator/gitcmd.py` (функции
  `git`/`branch_exists`), `orchestrator/auto.py` (импорты) — понадобилось,
  чтобы проверить утверждение PLAN про безвредность спецкейса `SpyRun`
  в `test_auto_cycle.py`, которое в пакете было только продекларировано,
  не показано кодом.

## Предложения системе
