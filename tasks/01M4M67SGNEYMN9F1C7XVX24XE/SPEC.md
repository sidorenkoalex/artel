---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_merge_gate.py, orchestrator/fsm_postmerge.py, orchestrator/retro.py, orchestrator/cleanup.py, orchestrator/snapshot.py, docs/codebase-map.md, tests/
budget_usd: 100
---

# SPEC: Этап 4 ADR-0021, часть A — мерж не кладёт в main снимок задачи и RETRO

## Контекст
ADR-0021 п.4 (этап 4) отменяет для всех проектов наложение снимка
`tasks/<id>/` на main и коммит RETRO в main. Сегодня шаг публикации мержа
`orchestrator/fsm_merge_gate.py::_publish_merge_artifacts` (~1040) делает
три вещи. Накладывает снимок ссылки документов (`_overlay_artifact_snapshot`
~356, коммит «<id>: снимок артефактной ветки поверх merge»), причём для
любого проекта. Проверяет его на посторонние файлы (`_guard_task_root_or_refuse`
~423; для артели ещё `_guard_all_or_refuse` ~485). Для артели коммитит
`docs/retro/<id>.md` и killed-RETRO долгов (`fsm_postmerge._generate_and_commit_retro`
~197). Долгом считается ликвидированная задача, у которой нет
`docs/retro/<id>.md` в дереве мержа.
Задача A переносит RETRO только в коммит закрытия `refs/artifacts/<id>`
(`orchestrator/snapshot.py`) и не даёт ему обеднеть. Проверку посторонних
файлов она переводит на дерево ссылки документов, а читателей, привязанных
к main, — на `refs/artifacts/<id>`. Решения Оператора по батчу вопросов —
`ANSWER-1.md`: п.1 — удаление тестов снятого механизма только вместе с
тестами-заменами; п.2 — наложение отменяется для всех проектов.

## Требования

1. Мерж задачи любого проекта (артели и внешнего) не кладёт в main
   каталог `tasks/<id>/`. Коммит «<id>: снимок артефактной ветки поверх
   merge» не создаётся (ADR-0021 п.4, ANSWER-1 п.2).
2. Мерж задачи артели не коммитит в main RETRO задачи
   (`docs/retro/<id>.md`, коммит «<id>: RETRO задачи») и killed-RETRO
   долгов (коммит «<id>: killed-RETRO долга <id>»). Коммиты, которые мерж
   кладёт в main: merge кодовой ветки, коммит приложений PLAN (если
   приложения были) и коммит карты кодовой базы (если в дереве мержа есть
   генератор карты, как сегодня).
3. RETRO задачи живёт только в `tasks/<id>/RETRO.md` коммита закрытия
   `refs/artifacts/<id>`. По содержанию оно не беднеет относительно
   сегодняшнего `docs/retro/<id>.md`: исход, счётчики, стоимость. Плюс:
   а) когда этот мерж применил приложения PLAN, в RETRO есть строка
      `fsm_postmerge.APPENDICES_RETRO_PREFIX` с их путями. Без приложений
      строки нет, а остальной текст RETRO не меняется ни одним символом
      (требование 6 SPEC 01M2YSHDKWFJN3XSJ618Z74FNF продолжает исполняться;
      ANSWER-1 п.1а);
   б) строка «Итог: done, sha …» несёт sha коммита мержа задачи в main
      проекта, а не `gitcmd.head_sha()` пульта. Это тот же коммит, на
      который сегодня адресуется `docs/retro/<id>.md`: merge кодовой ветки
      плюс приложения PLAN, без коммита карты (ANSWER-1 п.1б).
4. Провал коммита закрытия не отменяет перехода (`done` на пути мержа,
   `killed` на пути `kill`) и уборки задачи. Каждый такой провал поднимает
   incident-алерт с target этой задачи. Причины провала:
   - ссылки документов нет;
   - голова разошлась с фиксацией;
   - git не ответил;
   - `retro.build_done` или `retro.build_killed` бросили исключение.

   Это замена проверок «сбой → инцидент», которые уходят вместе с
   `tests/test_fsm_retro.py` (ANSWER-1 п.1в).
5. Ни один шаг мержа и постмержа не генерирует RETRO ликвидированных задач
   из-за отсутствия у них `docs/retro/<id>.md`. Механизм долгов заменяется
   так: RETRO ликвидированной задачи пишется коммитом закрытия на пути
   `kill`, а его провал виден Оператору инцидентом по требованию 4. Молча
   RETRO не пропадает (ANSWER-1 п.1г). Задачи, ликвидированные до этой
   задачи, механизм долгов уже обработал: до неё он запускался на каждом
   мерже артели.
6. Документы мержащейся задачи проверяются на дереве `refs/artifacts/<id>`
   на зафиксированной голове. Проверка идёт до push в main и до коммита
   закрытия, для всех проектов. Что даёт отказ мержа:
   - любого проекта — посторонний файл в `tasks/<id>/`, включая файлы
     глубже первого уровня. Критерий тот же, что сегодня у
     `_guard_task_root_or_refuse`;
   - для задачи артели — ещё и нарушения тех правил, которые сегодня
     `guard --all` дерева мержа применяет к `tasks/<id>/` этой задачи:
     посторонние файлы `acceptance_tests/`, маркер `AC-n` с отступом,
     структура `.md`-артефактов.

   Задачу не освобождает от проверки ни `docs/retro/<id>.md` в main или в
   дереве мержа, ни `RETRO.md` в ссылке. Отказ оформляется, как сегодня у
   `_guard_task_root_or_refuse`: запись журнала «merge FAILED», задача
   остаётся на `merge_gate` без эскалации, main origin не тронут
   (ANSWER-1 п.1д, п.2).
7. Если ссылка документов задачи недоступна или не читается на проверке
   требования 6, это отказ мержа тем же путём, что в требовании 6, а не
   пропуск проверки (ANSWER-1 п.1е).
8. `guard --all` по дереву мержа артели по-прежнему выполняется до
   вычисления sha для push, и видит он дерево уже с применёнными
   приложениями PLAN. В истории main порядок коммитов такой: merge кодовой
   ветки, затем коммит приложений PLAN, затем коммит карты кодовой базы
   (если она есть) (ANSWER-1 п.1ж).
9. Читатели, привязанные к main, работают и для задач, чьих документов в
   main нет, — по `refs/artifacts/<id>`:
   - `retro.build_done` без явного `address` пишет «Адрес артефактов:
     refs/artifacts/<id>», а не `<sha>:tasks/<id>/`;
   - `cleanup.artifacts_in_main` (признак «документы задачи сохранены
     историей», на нём строится `drop_task_dir`) для задачи без
     `tasks/<id>/` в main отвечает по наличию `refs/artifacts/<id>`.

   Исторические `docs/retro/*.md` и каталоги `tasks/*` в main остаются
   читаемыми, как сегодня.
10. Внешний проект: всё остальное в мерже не меняется. Требования 1, 3, 4,
    6 (первый пункт), 7 к нему относятся; RETRO в main, `guard --all` и
    прочие шаги, которых у внешнего проекта сегодня нет, не появляются
    (ANSWER-1 п.2).

## Критерии приёмки

AC-1. Мерж задачи артели в песочнице на настоящем git через
`_cmd_approve_merge_gate`. Задача в `done`. В истории main origin после
мержа нет коммитов с подстроками «снимок артефактной ветки поверх merge»,
«RETRO задачи» и «killed-RETRO долга». В дереве main origin нет
`tasks/<id>/` и `docs/retro/<id>.md`. Мутацию «наложение снимка оставлено»
этот критерий ловит.

AC-2. Тот же мерж. `tasks/<id>/RETRO.md` в `refs/artifacts/<id>` на
origin несёт «Итог: done», строку стоимости и счётчики задачи.

AC-3. Тот же мерж. sha в строке «Итог: done, sha …» RETRO закрытия совпадает
с sha коммита мержа задачи в main origin (merge кодовой ветки плюс
приложения PLAN, без коммита карты) и не совпадает с `gitcmd.head_sha()`
пульта.

AC-4. Мерж задачи с применимыми приложениями PLAN на настоящем git через
`_cmd_approve_merge_gate`. RETRO из `refs/artifacts/<id>` на origin
содержит ровно одну строку, которая начинается с
`fsm_postmerge.APPENDICES_RETRO_PREFIX` и перечисляет пути всех
применённых приложений. У мержа без приложений такой строки в RETRO нет.

AC-5. Мерж задачи артели с приложениями PLAN и генератором карты в дереве.
В истории main origin коммит приложений стоит после коммита merge кодовой
ветки и до коммита карты кодовой базы. `guard --all`, запущенный этим
мержем, видит дерево с уже применёнными приложениями. Тест краснеет от
перестановки `_apply_plan_appendices` за `_guard_all_or_refuse` и от
перестановки за вычисление sha для push.

AC-6. В БД есть задача в `killed` без `docs/retro/<id>.md` в main.
Следующий мерж другой задачи артели не коммитит в main её killed-RETRO:
`docs/retro/<killed-id>.md` в дереве main origin не появляется, коммита
«killed-RETRO долга» в истории нет.

AC-7. Путь мержа, по тесту на каждую причину провала коммита закрытия:
ссылки документов нет; голова разошлась с фиксацией; git не ответил;
`retro.build_done` бросил исключение. В каждом случае задача доходит до
`done`, уборка задачи выполнена, а в alerts есть открытый incident-алерт с
target этой задачи.

AC-8. Путь `kill`, по тесту на каждую причину провала коммита закрытия:
ссылки документов нет; голова разошлась с фиксацией; git не ответил;
`retro.build_killed` бросил исключение. В каждом случае задача в
`killed`, уборка выполнена, есть открытый incident-алерт с target этой
задачи.

AC-9. Мерж в песочнице на настоящем git. В `tasks/<id>/` на
зафиксированной голове `refs/artifacts/<id>` лежит посторонний файл:
отдельный прогон на первом уровне и отдельный в подкаталоге. В стенде
одновременно есть `docs/retro/<id>.md` в main и `tasks/<id>/RETRO.md` в
ссылке. Мерж отказан: в журнале «merge FAILED» с именем файла, задача на
`merge_gate`, голова main origin не сдвинулась. Это замена удаляемого
`tests/test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`.

AC-10. Мерж задачи артели. Посторонний файл в `tasks/<id>/acceptance_tests/`
на голове `refs/artifacts/<id>`: мерж отказан тем же путём, что в AC-9,
main origin не тронут.

AC-11. Мерж задачи, у которой ссылка `refs/artifacts/<id>` недоступна или
не читается на проверке документов задачи. Мерж отказан тем же путём, что
в AC-9, main origin не тронут.

AC-12. Мерж задачи внешнего проекта в песочнице на настоящем git. В
истории main проекта нет коммита «снимок артефактной ветки поверх merge»,
в дереве main проекта нет `tasks/<id>/` и `docs/retro/<id>.md`. Отдельный
прогон с посторонним файлом в документах задачи на голове
`refs/artifacts/<id>` даёт отказ мержа, как в AC-9.

AC-13. Читатели:
- `retro.build_done(conn, id, sha)` без `address` содержит «Адрес
  артефактов: refs/artifacts/<id>».
- `cleanup.artifacts_in_main` даёт «сохранены»:
  - для задачи, у которой `tasks/<id>/` нет в main, а `refs/artifacts/<id>`
    есть;
  - для задачи с историческим `tasks/<id>/` в main.
- Для задачи без ссылки и без каталога в main ответ — «не сохранены».

## Меняемое поведение

Удаление тестов снятого механизма разрешено мандатом ANSWER-1 п.1
(«Ослабление тестов разрешено: tests/test_fsm_retro.py,
tests/test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation,
tests/test_plan_appendix.py::MergeAppendixTest::test_appendix_commit_precedes_the_artifact_snapshot»).
Условие мандата — тесты-замены AC-4, AC-5, AC-7–AC-11. В
`test_appendix_commit_precedes_the_artifact_snapshot` по мандату удаляется
только `assertLess(applied[0], snapshot[0], subjects)`. Ниже — смены
ожидания, сверенные по коду main 415f1de4:

- `tests/test_plan_appendix.py::MergeAppendixTest::test_appendix_commit_precedes_the_artifact_snapshot`: `self.assertTrue(snapshot, f"нет коммита снимка: {subjects}")` → `self.assertEqual(snapshot, [], subjects)` (требование 1)
- `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::MergeGateStepsOnCloneTest::test_ac5_code_map_and_retro_are_committed_in_the_clone_merge_copy`: `self.assertIn(f"docs/retro/{task}.md", self.origin_tree(), self.msg(out))` → `self.assertNotIn(f"docs/retro/{task}.md", self.origin_tree(), self.msg(out))` (требование 2)
- `tests/test_retro_artifact_branch_reads.py::RetroBranchReadTest::test_done_address_names_the_snapshot_ref_when_asked`: `f"Адрес артефактов: {'abcd' * 10}:tasks/{TASK}/"` → `f"Адрес артефактов: refs/artifacts/{TASK}"` (требование 9)

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны 7 (порог 5); критериев приёмки 13
(порог 10); `budget_usd` 100 (порог $60).

**Обоснование монолита (материал для решения Оператора).** Деление на
задачи A и B Оператор уже провёл 11.10 (ТЗ, «Источник»). Внутри A
наложение снимка и проверка документов задачи меняются атомарно: проверки
`_guard_task_root_or_refuse` и `_guard_all_or_refuse` читают `tasks/<id>/`
наложенного дерева. Если снять наложение без переноса проверки на
`refs/artifacts/<id>` (требования 6–7), получится промежуточное состояние,
где посторонний файл уходит без отказа, — это ослабление, которого
требование 3 ТЗ не допускает. Перенос проверки без снятия наложения
оставляет в main то, что задача убирает. Отмена коммита RETRO в main
(требование 2) и полнота RETRO закрытия (требования 3–4) тоже связаны:
пока RETRO закрытия не несёт перечень приложений и sha мержа, отмена
RETRO в main обедняет историю задачи. А мандат ANSWER-1 п.1 разрешает
удалить тесты только вместе с заменами в одной ветке. Бюджет $100 —
решение Оператора 11.10 (ANSWER-1); он равен потолку ролей
`ROLE_BUDGET_CAP`.

## Не входит

- Исторические снимки для каталогов без `refs/artifacts` — задача B.
- Удаление `tasks/*` из main. Правка ссылок в скилах, шаблонах,
  `docs/invariants.md`, `docs/design-system.md`. Пересмотр ADR-0020 п.2.
  Всё это — коммит Оператора после A и B.
- Удаление исторических `docs/retro/*.md`. Пересчёт `orchestrator/budget.py`
  по `docs/retro/T*.md` не меняется.
- Мелкие строки RETRO: заметка killed («Адрес артефактов: артефакты не
  сохранены» у ликвидированной задачи остаётся). Строка sha в «Итог: done»
  в ТЗ была в «Не входит», но решением Оператора (ANSWER-1 п.1б) перенесена
  в требование 3б.
- Правка путей «только чтение» из ТЗ: `orchestrator/budget.py`,
  `orchestrator/doctor/`, `orchestrator/artifact_branch.py`,
  `orchestrator/store.py`, `orchestrator/config.py`, `orchestrator/catalog.py`,
  `orchestrator/fsm.py`, `orchestrator/acceptance.py`, `orchestrator/suite_run.py`,
  `orchestrator/suite_lock.py`, `scripts/` (включая правила
  `scripts/guard.py` и его пропуск отсутствующего `tasks/` в `--all`),
  `.github/workflows/ci.yml`, `tests/test_invariants.py`, `docs/`,
  `templates/`, `skills/`, `CLAUDE.md`, `models.yaml`, `roles.yaml`,
  `targets.yaml`, `tasks/`, `.artel/`. `orchestrator/snapshot.py` из этого
  перечня снят мандатом ANSWER-1 («Расширение зон разрешено»).
- Полный зелёный `tests/`, зелёный CI ветки, неизменность защищённых путей
  и бюджет (требование 6 ТЗ в части защищённых путей) — их держит пульт.

## Материалы

- ТЗ: `tasks/01M4M67SGNEYMN9F1C7XVX24XE/TZ.md`; ответ Оператора —
  `ANSWER-1.md`; ADR-0021 п.4 и этап 4
  (`docs/adr/0021-project-area-and-immutable-pult.md`).
- Узлы: `orchestrator/fsm_merge_gate.py` — `_overlay_artifact_snapshot`
  ~356, `_guard_task_root_or_refuse` ~423, `_guard_all_or_refuse` ~485,
  `_publish_merge_artifacts` ~1040, порядок вызовов в
  `_cmd_approve_merge_gate` ~1313–1330 (push, затем `_finalize_done_state`,
  затем `cleanup._commit_closing`, затем уборка); `orchestrator/fsm_postmerge.py` —
  `_generate_and_commit_retro` ~197, `APPENDICES_RETRO_PREFIX` ~183;
  `orchestrator/snapshot.py` — `_retro_with_frontmatter` ~34
  (`gitcmd.head_sha()` в «Итог: done»), `commit_closing` ~69;
  `orchestrator/cleanup.py` — `artifacts_in_main` ~12, `drop_task_dir` ~40,
  `_commit_closing` ~499; `orchestrator/retro.py::build_done` ~560 (адрес
  ~576).
- Свойства, которые остаются и чьи тесты не входят в «Меняемое поведение»
  (должны остаться зелёными без правки):
  - `tests/test_guard_task_root_subdirectory.py::MergeGateGuardRefusesSubdirectoryFileTest`
    — вызывает `_guard_task_root_or_refuse` напрямую с каталогом;
  - `tests/test_plan_appendix.py::RetroAppendicesLineTest` — зовёт
    `fsm_postmerge._with_appendices_line` и
    `fsm_postmerge.APPENDICES_RETRO_PREFIX`;
  - `tests/test_snapshot_closing_outcome.py` — форма «Итог: done, sha
    [0-9a-f]{40}» и адрес ссылки.
