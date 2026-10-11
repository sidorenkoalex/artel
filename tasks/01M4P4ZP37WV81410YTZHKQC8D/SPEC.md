---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/preflight.py, orchestrator/artel.py, orchestrator/fsm_advance.py, docs/codebase-map.md, tests/
budget_usd: 45
---

# SPEC: Предпроверка гейтов перехода для роли (шаг 1 порядка работ по тестам)

## Контекст
Сейчас роль узнаёт об отказе перехода только после того, как сдала шаг.
За 6 недель на выходе `tests_writing` было ~50 содержательных отказов,
отказов «замечания ревью не отработаны» — 327. «Сухого» перехода нет:
`artel.py advance` → `fsm.cmd_advance` (`orchestrator/fsm.py:589`) идёт
под lease и пишет журнал. `acceptance-dry-run` (`orchestrator/dry_run.py`)
проверяет только планку. По ответу Оператора (ANSWER-1, п.7) задача
сужена до предпроверки. Общий итог полного набора у `suite-run` и гейтов
(пункты 5–6 ТЗ в части итога) из неё исключён.

Классификация шагов выхода ниже сверена с кодом main 28cfe08c, а не
перенесена из перечня ТЗ (SPEC-AUDIT, отклонения 5–8).

## Требования

1. Новая команда `artel.py preflight <id>`. Для задачи в состоянии
   `tests_writing` или `in_dev` она проходит шаги выхода из этого
   состояния (`orchestrator/fsm_advance.py`, функции `tests_writing` и
   `in_dev`) в том же порядке, что и переход. По каждому шагу печатается
   ровно одна строка: «пройден», «отказ: <текст отказа>» либо «не
   проверяется предпроверкой: <почему>». На отказе предпроверка не
   останавливается: она печатает и остальные шаги цепочки.
2. «Текст отказа» гейта, возвращающего `GateRefusal`, — это поля `detail`
   и `hint` того `GateRefusal`, который тот же гейт возвращает переходу на
   той же задаче, побайтно.
3. Шаги с побочными эффектами предпроверка не исполняет, а печатает по
   ним «не проверяется предпроверкой: <почему>». Это как минимум:
   - на выходе `tests_writing`: эскалация по пометкам `escalate`
     (`store.set_state`, fsm_advance.py:493–510); гейт групп
     `_tests_writing_test_groups_gate` (требует выкладки планки в рабочую
     копию, fsm_advance.py:533–541); сухой сбор
     `_tests_writing_dry_collect_gate`; манифест долгоживущих тестов
     `_tests_writing_manifest_gate` (коммит в ссылку документов); смена
     состояния и фиксация `tests_locked_sha`;
   - на выходе `in_dev`: сверка незакоммиченного результата шага
     (`fsm._dirty_refuses`); эскалация по `status: escalate` PLAN.md;
     `_acceptance_lock_refuses`; подтяжка main
     (`fsm._pull_main_or_escalate`); `_long_lived_manifest_refuses`;
     `_zones_gate` при мандате; `_plan_appendix_gate` (рабочая копия);
     двусторонний прогон гейта неослабления; `_origin_push_gate` (push);
     `_acceptance_run_refuses` (прогон планки); бюджет из PLAN,
     `merge_after.apply_plan` и смена состояния.
4. Чистые шаги предпроверка исполняет. На выходе `tests_writing` это
   `_project_profile_gate`, `_tests_writing_code_diff`,
   трассируемость AC (требование 5), `_tests_writing_stray_plank_files_gate`,
   `code_copy` (требование 6) и `_tests_writing_long_lived_gate`. На выходе
   `in_dev`: статус PLAN.md и его структура (через `guard.check_content`),
   `_answer_gate`, `_capacity_gate`, `_zones_gate` без мандата,
   `_mutation_claim_gate`, ядро гейта неослабления (требование 7),
   `_review_rework_gate` и `_network_address_gate`.
5. Трассируемость AC, маркер красноты и образец id на выходе
   `tests_writing` предпроверка проверяет теми же публичными ядрами
   `scripts/guard.py`, что и переход: `guard.scan_ac_content`,
   `guard.traceability_errors_from_content`,
   `guard.redness_marker_errors_from_files`, `guard.id_format_sample_errors`,
   `guard.check_content`. Планку она читает из ссылки документов задачи,
   не выкладывая её в рабочую копию кода. На той же планке строки ошибок
   совпадают с теми, что переход пишет в журнал под действием «переход
   отклонён: трассируемость AC». `orchestrator/fsm.py` не меняется.
6. `code_copy` на выходе `tests_writing`: предпроверка только проверяет,
   что рабочая копия задачи уже заведена и выписана на кодовую ветку
   задачи. Ничего она не заводит (`workspace.ensure` не зовётся). Если
   копии нет или она на чужой ветке, печатается отказ с действием
   `CODE_COPY_REFUSAL_ACTION` и тем же `hint`, что у
   `_tests_writing_code_copy_gate`. Копия на чужой ветке даёт тот же
   `detail`, что у перехода.
7. Гейт неослабления тестов: предпроверка исполняет его чистое ядро
   `_evaluate` (`orchestrator/advance_gates/test_integrity.py`) без
   двустороннего прогона и без записи в журнал. Отказ печатается с
   `detail` = `refusal_detail(ev.rest)` и `hint` = `_mandate_hint` того же
   модуля, а при отказе git — тем же `detail`/`hint`, что у
   `_test_integrity_gate`. Если ядро не дало непокрытых находок, но есть
   методы смены ожидания (исход 7а, test_integrity.py:1350–1355),
   печатается «не проверяется предпроверкой: смена ожидания требует
   двустороннего прогона», а не «пройден». Модуль `test_integrity.py` не
   меняется.
8. Проекту без профиля тестов гейты, которые в переходе пишут
   `project_profile.journal_skip` (`_mutation_claim_gate`, гейт
   неослабления, проверки долгоживущих файлов и групп на выходе
   `tests_writing`), не исполняются. Предпроверка сама сверяет
   `project_profile.decide` и печатает «не проверяется предпроверкой: у
   проекта нет профиля тестов». Журнал при этом не пишется.
9. Вывод `preflight` для `in_dev` содержит строку о том, что ветка
   проверена без подтяжки main и после подтяжки исход `capacity`,
   `mutation_claim` и `network_address` может разойтись.
10. `preflight` только читает. Она не берёт lease и не пишет журнал
    (`store.journal`). Она не делает коммитов и push, не заводит и не
    меняет рабочих копий, не выкладывает планку
    (`acceptance.materialize_from_branch`) и не меняет состояние задачи,
    её ветку и ссылку документов.
11. Код выхода `preflight`: 0, если все исполненные шаги пройдены; 1, если
    есть хотя бы один отказ; 2, если задача в состоянии, для которого
    предпроверки нет (любое, кроме `tests_writing` и `in_dev`).
12. `preflight` работает и тогда, когда БД пульта открыта только на чтение
    (роль под песочницей Codex). Для этого у неё запасной путь открытия
    без миграции и смены режима журнала, тем же приёмом, что у
    `suite-run` (`orchestrator/suite_run.py:149–159`).
13. `preflight` входит в `_ROLE_ALLOWED_COMMANDS`
    (`orchestrator/artel.py`), то есть разрешена из окружения роли.
14. Приложение PLAN к `skills/conventions-core.md` указывает роли
    запускать `artel.py preflight <id>` перед сдачей шага.
15. Порядок шагов и их тексты у предпроверки и у перехода берутся из
    одной точки правды. Это объявленный реестр шагов выхода
    `tests_writing` и `in_dev`: имя шага, вызываемое и либо признак
    «исполняется предпроверкой», либо причина «не проверяется».
    Переходы `tests_writing`/`in_dev` идут по этому реестру, и шаг,
    добавленный в реестр, попадает в `preflight` без правки `preflight`.
    Обёртки `_capacity_gate_refuses`, `_zones_gate_refuses`,
    `_plan_appendix_gate_refuses`, `_test_integrity_gate_refuses` и
    `_review_rework_gate_refuses` сохраняют имена и сигнатуры и зовутся из
    реестра. Порядок, журнал и stdout перехода не меняются. Правка
    `orchestrator/fsm_advance.py` этим выносом и ограничена.
16. Тест-сторож сверяет реестр с переходом и с `preflight`. Он ловит
    шаг перехода, которого нет в реестре; шаг с побочным эффектом,
    помеченный исполняемым (предпроверка в тесте исполняется под
    заглушками, запрещающими `store.journal`, коммит, push,
    `workspace.ensure` и `acceptance.materialize_from_branch`); и
    расхождение ядер трассируемости у предпроверки и перехода.

## Критерии приёмки

AC-1. В песочнице задача в `in_dev` нарушает ровно один чистый гейт
(например, `_network_address_gate`). `preflight <id>` печатает строку
отказа этого гейта, её `detail` и `hint` побайтно совпадают с
`GateRefusal`, который тот же гейт возвращает `advance` той же задачи, и
команда завершается с кодом 1.

AC-2. В сценарии AC-1 после `preflight` не изменились журнал задачи,
lease, состояние задачи, голова и рабочее дерево ветки задачи и голова
ссылки документов. Коммитов и push нет.

AC-3. Задача в `tests_writing`, у планки которой AC-n не покрыт ни
тестом, ни пометкой. `preflight` печатает отказ трассируемости с теми же
строками ошибок, что `advance` пишет в журнал под действием «переход
отклонён: трассируемость AC», и завершается с кодом 1.

AC-4. Задача в `tests_writing`, рабочая копия кода не заведена.
`preflight` печатает отказ `code_copy` с действием
`CODE_COPY_REFUSAL_ACTION` и `hint` перехода и завершается с кодом 1.
Рабочая копия после этого так и не заведена, планка в рабочую копию не
выложена. Журнал, lease, состояние, ветка и ссылка документов не
изменились.

AC-5. Задача в `tests_writing` с заведённой рабочей копией, все
исполняемые шаги пройдены. `preflight` завершается с кодом 0. Гейт групп
напечатан строкой «не проверяется предпроверкой: требует выкладки
планки», сухой сбор и манифест — строками «не проверяется
предпроверкой: <почему>».

AC-6. Задача в `in_dev`, все чистые гейты пройдены. `preflight` печатает
«пройден» по каждому исполненному шагу и завершается с кодом 0. Каждый
шаг с побочным эффектом из требования 3 для `in_dev` напечатан строкой
«не проверяется предпроверкой: <почему>». В выводе есть строка о
проверке без подтяжки main с упоминанием `capacity`, `mutation_claim` и
`network_address`.

AC-7. Задача в `in_dev` ослабляет тест в `tests/` без мандата.
`preflight` печатает отказ гейта неослабления с `detail` =
`refusal_detail(ev.rest)` и `hint` = `_mandate_hint` модуля
`test_integrity.py` и завершается с кодом 1. `two_sided.run` не вызван,
журнал задачи не изменился.

AC-8. Задача в `in_dev` без непокрытых находок неослабления, но с
методом смены ожидания из раздела SPEC «Меняемое поведение».
`preflight` печатает по гейту неослабления «не проверяется
предпроверкой: смена ожидания требует двустороннего прогона», а не
«пройден». `two_sided.run` не вызван.

AC-9. Задача проекта без профиля тестов в `in_dev`. `preflight` печатает
по `_mutation_claim_gate` и гейту неослабления «не проверяется
предпроверкой: у проекта нет профиля тестов». Журнал задачи не
изменился: записи `journal_skip` нет.

AC-10. Задача в состоянии вне `tests_writing`/`in_dev` (`spec_writing`,
`review`, `verifying`). `preflight` завершается с кодом 2.

AC-11. Мутация «новый чистый гейт добавлен в переход, но не в
`preflight`» ловится тестом-сторожем.

AC-12. Мутация «шаг с побочным эффектом помечен в реестре исполняемым»
ловится тестом-сторожем: предпроверка под заглушками, запрещающими
`store.journal`, коммит, push, `workspace.ensure` и
`acceptance.materialize_from_branch`, роняет тест.

AC-13. Мутация «предпроверка проверяет трассируемость не тем ядром
`guard.*`, что переход» ловится тестом-сторожем.

AC-14. `preflight` из окружения роли разрешена
(`_ROLE_ALLOWED_COMMANDS`), и при БД, открытой только на чтение, команда
отрабатывает с тем же выводом и кодом выхода, что при БД на запись.

AC-15. Приложение PLAN к `skills/conventions-core.md` после наложения
даёт в скиле указание роли запускать `artel.py preflight <id>` перед
сдачей шага.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (`orchestrator/preflight.py`,
`orchestrator/artel.py`, `orchestrator/fsm_advance.py`,
`docs/codebase-map.md`, `tests/`); критериев приёмки ≥ 10 (15);
`budget_usd` ≥ $30 (45).

Деление уже сделал Оператор: общий итог полного набора исключён
(ANSWER-1, п.7, «C — только предпроверка», `budget_usd` не выше 50).
Предлагается монолит. Резать оставшееся нельзя, потому что реестр шагов
выхода и предпроверка — одна механика. Реестр без потребителя
мёртв, и сторож требования 16 на нём ничего не сверяет. Предпроверка без
реестра нарушает «одну точку правды» пункта 4 ТЗ: перечень шагов в ней
пришлось бы вести руками. Решение о монолите — за Оператором на гейте
SPEC.

Бюджет $45 — по калибровке «до 15 критериев и до 7 файлов», в пределах
рамки ТЗ ($50) и ответа Оператора.

## Не входит

- Общий итог полного набора у `suite-run` и гейтов (пункты 5–6 ТЗ в
  части итога) исключён ответом Оператора (ANSWER-1, п.7): итог,
  полученный процессом роли, создаёт риск обхода гейта полного набора.
  Свойство «гейт берёт только свои записи»
  (`tests/test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py::SuiteReuseTest::test_ac12_suite_run_record_is_not_gate_result`)
  сохраняется. `orchestrator/suite_run.py` и `orchestrator/acceptance.py`
  только читаются.
- Дедупликация прогонов CI push/pull_request (строка бэклога «CI ветки
  задачи — полный набор один раз на sha»): отдельная задача, `ci.yml`
  приложением.
- Предпроверка состояний `spec_writing`, `verifying`, `review`.
- Исполнение предпроверкой шагов с побочными эффектами, двустороннего
  прогона гейта неослабления, гейта групп и сверки незакоммиченного
  результата шага.
- Смена поведения переходов, гейтов и их отказов (пункт 6 ТЗ).
- Правка `tests/test_zones_gate.py`, `tests/test_capacity_gate.py`,
  `tests/test_fsm_review_rework_gate.py`,
  `tests/test_fsm_advance_gate_smoke.py`: они не правятся и остаются
  зелёными (ANSWER-1, п.5). Зелёный полный набор `tests/` держит пульт.
- Правка `skills/conventions-core.md` в ветке задачи: защищённый путь
  меняется только приложением PLAN (требование 14). Применимость
  приложения (`git apply --check`) держит пульт гейтом приложений.
- Правка путей «только чтение» ТЗ: `orchestrator/dry_run.py`,
  `orchestrator/advance_gates/test_integrity.py`,
  `orchestrator/advance_gates/two_sided.py`, `orchestrator/answer.py`,
  `orchestrator/advance_gates/mandate.py`, `scripts/guard.py`,
  `orchestrator/fsm.py`, `orchestrator/config.py` (кроме новой константы,
  если она нужна), `tests/test_invariants.py`, `docs/invariants.md`,
  `docs/adr/`, `docs/operator-gates.md`, `docs/backlog.md`, `templates/`,
  `CLAUDE.md`, `roles.yaml`, `.github/`, `.artel/`.

## Материалы

- ТЗ: очередь Оператора 11.10 «Порядок работ по тестам конвейера», шаг 1.
- ANSWER-1.md (решение Оператора 11.10.2026: 7 — C, 3 — A, 4 — A/B,
  5 — A); SPEC-AUDIT.md (возврат 1, отклонения 5–14).
- `orchestrator/fsm_advance.py:458–575` (`tests_writing`), `:664–768`
  (`in_dev`), `:705–712` (обёртки R2); `orchestrator/advance_gates/_base.py`
  (`_run_gates`); `orchestrator/advance_gates/tests_writing.py:239–273`
  (`_tests_writing_acceptance_dir`, `_tests_writing_code_copy_gate`);
  `orchestrator/advance_gates/test_integrity.py:1292–1366`
  (`_test_integrity_gate`); `orchestrator/advance_gates/review.py:184,213–216`
  (`_mutation_claim_gate`, `journal_skip`); `orchestrator/fsm.py:501–586`
  (`_tests_writing_ac_state`); `orchestrator/suite_run.py:149–159` (БД
  только на чтение).
