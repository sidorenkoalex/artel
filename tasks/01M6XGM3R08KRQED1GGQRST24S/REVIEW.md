---
task: 01M6XGM3R08KRQED1GGQRST24S
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Поверхность решения и размер проверки в критериях SPEC — правила для analyst, аудитора, test_author и ревьювера (ADR-0032, этап 3)

## Соответствие SPEC

Фаза A (план): таблица покрытия полна (требования 1–3 → шаги 1–3); шаги
проверяемые; подход — приложения PLAN для защищённых путей, код пульта
не трогается — соответствует конвенциям и прецеденту 01M5NHXJA3X7C66XTJN4J3E25W.
«Влияние на систему» совпадает с фактическим diff (`git diff --stat d87d7d7ce HEAD`:
только `docs/codebase-map.md` и новый `tests/test_01m6xgm3r08krqed1ggqrst24s_criterion_form.py`).
Откат описан (revert merge-коммита).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Хвост PLAN.md от `\n## Приложение 1 ` до конца байт в байт равен такому же хвосту TZ.md (сравнение строк в python — `True`). `scripts.guard.plan_appendices(PLAN)` отдаёт 5 приложений, ошибок разбора нет; каждое проходит `git apply --check` на HEAD `6f86f6de`. Планка AC-1 зелёная. |
| 2 | OK | Долгоживущий файл test_author на месте, 7 тестов зелёные; AC-2…AC-5 покрыты; у каждого метода есть «Ловит мутацию: …» с наблюдаемым расхождением (пустой/непустой `check_content`, число и вид ошибок сверки покрытия); AC-5 сам вносит мутацию `PLAIN_NUMBERED_ITEM` и проверяет краснеющий AC-2, так что чувствительность сторожа доказана в самом наборе. Малый размер выдержан: только строки в памяти, без git, БД и процессов. |
| 3 | OK | Вне `tests/` изменена только `docs/codebase-map.md`: в diff есть новый раздел файла теста, `Импортируется` у `scripts/guard.py` и `built_at_sha`. Других путей нет. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved — блокеров и major нет. Пять приложений перенесены из ТЗ без
изменений и чисто накладываются. Тесты, читающие шаблон и скилы, на
дереве с наложенными приложениями зелёные. Сторож совместимости формы
критерия с guard лежит в `tests/` и доказанно чувствителен (AC-5).

## Проверено исполнением

- Сравнение в python хвоста PLAN.md с хвостом TZ.md от заголовка
  `## Приложение 1 ` до конца — `equal True`.
- `scripts.guard.plan_appendices(PLAN.md)` → 5 приложений, ошибок разбора нет; `git apply --check` каждого на HEAD → код 0 у всех пяти.
- `python3 -m pytest tests/test_01m6xgm3r08krqed1ggqrst24s_criterion_form.py -p no:cacheprovider -q` → 7 passed.
- `artel.py plank-run 01M6XGM3R08KRQED1GGQRST24S` → 5 passed, код выхода pytest 0.
- Временная копия дерева HEAD (`git archive` во временный каталог вне рабочей копии) с наложенными `patch -p1` пятью приложениями. В ней `templates/SPEC.md` несёт 2 вхождения «Размер проверки» и прогнаны:
  - `tests/test_01m4rzbdfshnessbqreh5mky9b_role_templates.py` вместе с долгоживущим файлом задачи → 23 passed, 32 subtests passed;
  - тесты, читающие шаблон, скилы или приложения: `test_01m5aa5ts90rdj2afxb882wtpd_template_hints`, `test_guard_division_section`, `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units`, `test_guard_path_mentions`, `test_analyst_role`, `test_agent_prompt`, `test_spec_budget`, `test_guard_zones`, `test_ci_protected_paths` → 147 passed, 86 subtests passed.
  - После прогона копия удалена.
- Карта: перегенерировать её в копии без git не удалось (`codebase_map.py` зовёт `git rev-parse`). Содержимое проверено по `git diff d87d7d7ce HEAD -- docs/codebase-map.md`: оно соответствует новому файлу теста. CI коммита `6f86f6de` зелёный.

## Предложения системе

- Пакет ревью показывает «Diff: (изменений нет)», когда ветка меняет только исключённые из пакета файлы (карту и долгоживущий тест из перечня лока). Это легко принять за пустую ветку. Стоит писать в пакете «изменения есть только в исключённых файлах: …» (`orchestrator/` — сборка ревью-пакета).
