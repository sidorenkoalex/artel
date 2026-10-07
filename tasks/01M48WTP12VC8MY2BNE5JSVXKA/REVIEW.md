---
task: 01M48WTP12VC8MY2BNE5JSVXKA
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Вынос повторяющейся подготовки тестов в tests/sandbox.py (ревизия тестов TR-23..25)

## Фаза A: план

- В таблице покрытия PLAN есть требования 1–6 и три возврата: шаг 4 — `maintenance.lock`, шаг 5 — R1-F1/R1-F2, шаг 6 — размер проекции карты. Покрытие полное.
- Шаги 5 и 6 проверяемые и по размеру укладываются в MR. «Влияние на систему» по-прежнему совпадает с диффом: изменены только `tests/`, в том числе первые строки докстрингов модулей (их требует шаг 6).
- Кандидат `tests/test_invariants.py:1602` — защищённый путь. Он записан в PLAN строкой для Оператора («Риски»), как и предлагалось в R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: шаблоны создаются один раз на процесс, наружу отдаётся только копия, `setUpClass`/`setUpModule` нет. |
| 2 | OK | Все пути создания bare-origin идут через `init_bare_origin` (`tests/sandbox.py:959-965`, `-b config.MAIN_BRANCH`). |
| 3 | OK | Теперь на помощник переведены и `tests/test_pin.py:99`, `tests/test_workspace.py:60`, `tests/test_multitarget_invariants.py:203`. grep `--bare` по `tests/` вне долгоживущих находит только помощник, защищённый `test_invariants.py:1602` и два `git clone --bare` (`test_workspace.py:429`, `test_doctor_closed_ref_fix.py:29`). `clone --bare` — другая операция: она клонирует готовый репозиторий, а не создаёт пустой origin, поэтому копией не считается. |
| 4 | OK | Замеры по ANSWER-1 (шесть строк с нагрузкой и оговоркой) и собственный замер `setUp` до/после. |
| 5 | OK | В инкрементальном диффе нет ни одной изменённой строки `assert*`. Изменены только импорты, строки подготовки и докстринги. В `test_workspace.py` вызов `init_bare_origin(self.origin, self.git)` передаёт ту же `self.git` с теми же аргументами, что прежний `self.git("init", ...)`. В `test_pin.py` и `test_multitarget_invariants.py` прежний `subprocess.run(..., check=True, capture_output=True)` заменён на `_REAL_RUN(...)` с теми же флагами. `subprocess` в обоих файлах по-прежнему используется (8 и 5 вызовов), неиспользуемого импорта нет. |
| 6 | OK | Долгоживущий файл задачи (AC-1/2/3/5) и `test_sandbox.py::SandboxFixtureBuildersTest`. Докстринги теперь начинаются со сценария (R1-F2). |

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_pin.py:99; tests/test_workspace.py:60; tests/test_multitarget_invariants.py:203 | дословные копии заведения bare-origin не переведены на `init_bare_origin` (AC-7 неполон) | TR-24 закрыт частично | Все три места переведены, поведение (флаги, `check`, git-обёртка) сохранено. grep подтверждает: других копий `git init --bare` вне долгоживущих и защищённого `test_invariants.py` не осталось, а последний записан в PLAN кандидатом для Оператора. Принято. |
| R1-F2 | accepted | tests/test_sandbox.py:115; tests/test_sandbox.py:134 | докстринг — только заявка мутации, без сценария и свойства | неясно, что проверяет тест | В обоих докстрингах первой строкой стоит сценарий с наблюдаемым свойством, заявка мутации сохранена. Принято. |

## Вердикт

approved. R1-F1 и R1-F2 закрыты. Укороченные докстринги модулей (возврат по проекции карты) смысл не теряют: подробности перенесены ниже в те же докстринги. Новых дефектов не нашёл.

## Проверено исполнением

- `python3 -m pytest tests/test_pin.py tests/test_workspace.py tests/test_multitarget_invariants.py tests/test_sandbox.py tests/test_codebase_map.py tests/test_01m48wtp12vc8my2bne5jsvxka_sandbox_copies.py -q -p no:cacheprovider -p timeout -o timeout=120` — 97 passed, 2 subtests passed за 112,61 с.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M48WTP12VC8MY2BNE5JSVXKA` — 5 passed за 3,44 с, код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: дифф только в `built_at_sha`, без этой строки расхождений нет — карта свежа. Перегенерированный файл откатил (`git checkout`), `git status` чист.
- grep `--bare` по `tests/` (результат в строке требования 3).
- AC-8: `git diff f020d43c HEAD --stat -- 'tests/test_01m*'` (f020d43c — main, подтянутый в da7c480f) показывает изменение только собственного долгоживущего файла задачи. Сравнение с локальным `main` (f341e7c0) даёт ещё 5 файлов, но они пришли подтяжкой более свежего main, ветка их не трогала.
- В инкрементальном диффе нет ни одной строки `self.assert*`/`assert` среди `-`/`+` (проверено глазами по всему диффу пакета: 5 файлов, 31+/22−).

## Предложения системе

- Ревью-пакет / AC-8: локальная ветка `main` в worktree отстаёт от main, подтянутого в ветку задачи (f341e7c0 против f020d43c). Поэтому `git diff main...HEAD -- tests/test_01m*`, который пакет рекомендует для полного диффа, показывает чужие долгоживущие файлы как изменённые. Стоит, чтобы пакет называл фактическую базу сравнения (sha подтянутого main), а не локальный `main`.
