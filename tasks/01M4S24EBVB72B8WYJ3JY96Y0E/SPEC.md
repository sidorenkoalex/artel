---
task: 01M4S24EBVB72B8WYJ3JY96Y0E
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/brief.py, orchestrator/fsm_merge_gate.py, orchestrator/config.py, tests/, docs/codebase-map.md
merge_after: 01M4S24963R9H18AN2XDP6R15B, 01M4RZBDFSHNESSBQREH5MKY9B, 01M4RZBPG6EXM74MTBPTEGW2D4
budget_usd: 45
---

# SPEC: Справочник ядра в брифе и пересборка после мержа (К-3б)

## Контекст
Решение Оператора 12.10.2026 (план обогащения ролей знаниями, задача 3 из 4,
полный вариант 13.10), часть «б». Часть «а» (01M4S24963R9H18AN2XDP6R15B)
даёт генератор `scripts/core_reference.py`, проверку поля `core_reference`
записи проекта и кэш `reference_cache.get_reference(conn, task_id, *,
reason, sha=None)` → `text`, `note`, `state` (`off`/`fresh`/`cached`/
`unverified`/`absent`) с журналом сборки и алертами сбоев. Эта часть —
потребители интерфейса: компонент справочника в брифе developer и
test_author, предел размера с алертами, сборка справочника после мержа и
настройка артели приложением к `targets.yaml`. Цель — короткий ответ «как
пользоваться» ядром порядка 5–10 тыс. токенов на шаг (замер прототипа на
b13c9e87: около 26,7–26,8 КБ на настройке артели из приложения).

Сейчас (main b13c9e87): `orchestrator/brief.py::developer_brief` (~677)
собирает SPEC, проекцию карты, `CLAUDE.md`, PLAN/REVIEW, ANSWER через
`_manifest_component` (~386); пометка стухлости карты `map_note` идёт перед
компонентом вне хэшируемого текста (~718–731); `test_author_answer_component`
(~1017) — добавка брифа test_author (без причины возврата и ANSWER —
`None`). Шаг после мержа в `fsm_merge_gate._cmd_approve_merge_gate`:
`_push_merged_main` (~1329) → `_finalize_done_state` (~1331) →
`cleanup._commit_closing` (~1332).

## Требования

1. Бриф developer несёт компонент справочника из
   `reference_cache.get_reference(conn, task_id, reason="brief")` — сразу
   после проекции карты и до конвенций (`CLAUDE.md`).
2. Бриф test_author несёт тот же компонент после причины возврата и ANSWER
   (внутри результата `test_author_answer_component`); при справочнике или
   при `note` без компонента (`absent`) `test_author_answer_component` не
   возвращает `None`; при `state == "off"` — `None`, как прежде. Новая запись
   «бриф: компонент» у test_author появляется только при справочнике
   (осознанное расширение описи).
3. Reviewer, analyst и spec_auditor справочник не получают.
4. `state == "off"` — бриф developer и test_author байт в байт прежний: ни
   компонента, ни пометки, ни записи журнала. Проект без поля
   `core_reference` работает байт в байт как сейчас, кроме случая
   нечитаемого `targets.yaml` (исключение из матрицы неослабления ТЗ): тогда
   бриф несёт пометку, поднимается алерт (исход К-3а — `absent` с пометкой
   и алертом), бриф и мерж не останавливаются.
5. Компонент у обеих ролей оформлен через `_manifest_component`: метка с
   относительным путём кэша
   `.artel/projects/<проект>/knowledge/derived/core-reference.md` (без
   домашнего каталога), размер и sha256 в описи, запись «бриф: компонент» с
   sha256 в журнал, граница недоверенных данных.
6. `note` (не сверен, отсутствует, сбой) выводится, если она непуста, при
   любом `state` (согласовано с требованием 7 К-3а: например, `fresh` при
   незаписанном кэше несёт пометку); идёт ПЕРЕД компонентом и в хэшируемый
   текст не входит — тем же приёмом, что `map_note`. Пустая `note` пометки
   не даёт. При `state == "absent"` — только `note`, без компонента.
7. Предел `config.CORE_REFERENCE_MAX_BYTES = 32_768` в байтах UTF-8.
   Справочник крупнее предела в бриф не идёт; вместо него строка
   «справочник ядра: <размер> байт > <предел> — не включён, решение за
   Оператором (сузить настройку проекта или поднять предел)» без указания
   читать файл адресно; поднимается алерт вида `incident` источника
   `brief.core_reference_oversized` по проекту задачи. Размер снова в
   пределе — открытый алерт этого источника и этого проекта снимается
   автоматически (образец `brief._handle_map_size_alert`). Тексты алертов —
   без размеров и sha.
8. Предупреждение до предела: размер больше 90% предела и не больше предела
   — алерт вида `warning` источника `brief.core_reference_near_limit` по
   проекту задачи; снимается автоматически, когда размер не больше 90%
   предела или когда поднят алерт предела (требование 7).
9. Шаг после мержа в `fsm_merge_gate._cmd_approve_merge_gate`: сразу после
   `_finalize_done_state` и до `cleanup._commit_closing` вызывается
   `get_reference(conn, task_id, reason="merge", sha=final_sha)` для проекта
   задачи (у проекта без поля при читаемом `targets.yaml` — `off`, без
   побочных эффектов; нечитаемый `targets.yaml` — пометка и алерт К-3а, мерж
   не останавливается). Шаг ничего не
   коммитит и дерево мержа не меняет; при исходе `"moved"` у
   `_push_merged_main` не вызывается. Весь шаг, включая запись журнала и
   алерта в обработчике сбоя, исполняется под `try/except Exception`;
   помощников, завершающих процесс (`sys.exit`, например
   `brief._main_branch_text`), шаг не вызывает. Сбой, зависание или
   остановка процесса в шаге не оставляют задачу в `merge_gate` при
   обновлённом `main`. Срок — общий срок сборки К-3а (60 с).
10. PLAN.md задачи содержит раздел «## Приложение» с блоком diff к
    `targets.yaml`, добавляющим в конец записи `artel`, после строки
    `full_suite_timeout_sec: 1500`, комментарий-пояснение и блок ниже
    (отступы буквальные: `core_reference:` — 4 пробела, подполя — 6; шапку
    файла не трогать):
    ```yaml
        core_reference:
          modules: [orchestrator/store.py, orchestrator/config.py, tests/sandbox.py, orchestrator/fsm.py, orchestrator/runner.py, orchestrator/gitcmd.py]
          constants_module: orchestrator/config.py
          constants: [PROTECTED_PATHS, COMMON_ZONES, STATE_ROLE, DEFAULT_TARGET, PROJECT_DIRS, MAIN_BRANCH, ROOT, TASKS, PROJECTS, TARGETS, DB, LOGS]
    ```
    `guard.plan_appendices(PLAN)` возвращает ровно одно приложение с путём
    `targets.yaml`. Проверка Оператора после мержа: в журнале мержа есть
    «приложения применены: targets.yaml»; после `pin-update` первый бриф
    developer или test_author артели несёт компонент справочника и запись
    «справочник ядра: построен»; нет — правка `targets.yaml` Оператором
    (`doc-commit`). Отдельного алерта «поле отсутствует» нет.
11. Тесты в `tests/` с заявками «Ловит мутацию» на временном `targets.yaml`
    и области проектов песочницы (настоящие `targets.yaml` и
    `.artel/projects` не читаются и не пишутся) ловят мутации, перечисленные
    в AC-1…AC-12. Существующие тесты не ослабляются; ожидания тестов,
    названных в «Меняемом поведении», при отсутствии поля не меняются.
12. `docs/codebase-map.md` обновляется в той же задаче.

## Критерии приёмки

AC-1. При справочнике (`fresh`/`cached`) бриф developer содержит компонент
справочника, стоящий после проекции карты и до компонента `CLAUDE.md`; в
журнале задачи есть запись «бриф: компонент» для него (ловит: компонент не
дошёл до developer; стоит не после проекции карты / не между проекцией
карты и `CLAUDE.md`; нет записи журнала).

AC-2. При справочнике `test_author_answer_component` возвращает не `None` и
содержит компонент справочника после причины возврата и ANSWER; в журнале
есть запись «бриф: компонент» для него (ловит: `None` при справочнике;
компонент до ANSWER; нет записи журнала).

AC-3. Ревью-пакет reviewer, бриф analyst и бриф spec_auditor не содержат
компонента справочника и пометки о нём при поле `core_reference` в записи
проекта (ловит: справочник дошёл до reviewer/analyst/spec_auditor).

AC-4. При `state == "off"` бриф developer и бриф test_author байт в байт
совпадают с эталоном — брифом той же задачи без поля `core_reference` в
записи проекта (читаемый `targets.yaml`), новых записей журнала нет,
`test_author_answer_component` без причины возврата и ANSWER возвращает
`None` (ловит: при `off` бриф изменился). При нечитаемом `targets.yaml`
бриф developer строится и несёт пометку, поднят алерт, исключения нет
(ловит: нечитаемый `targets.yaml` остановил бриф).

AC-5. Компонент справочника несёт метку с относительным путём
`.artel/projects/<проект>/knowledge/derived/core-reference.md` без
домашнего каталога, обёрнут границей недоверенных данных; размер и sha256
в описи совпадают с размером и sha256 текста справочника, sha256 в записи
журнала «бриф: компонент» совпадает с sha256 текста справочника.

AC-6. При `state == "unverified"` и при `fresh` с непустой `note` (кэш не
записан) `note` стоит перед компонентом и не входит в хэшируемый текст
(sha256 описи равен sha256 текста справочника без `note`); при пустой
`note` (`fresh`/`cached`) пометки нет (ловит: `note` внутри хэшируемого
текста; пометка не перед компонентом; непустая `note` отброшена по
`state`; пометка при пустой `note`).

AC-7. При `state == "absent"` бриф developer и результат
`test_author_answer_component` несут только `note`, без компонента и без
записи «бриф: компонент»; `test_author_answer_component` при этом не
`None` (ловит: пустой компонент вместо пометки).

AC-8. Предел берётся из `config.CORE_REFERENCE_MAX_BYTES` (значение
`32_768`) и считается в байтах UTF-8: справочник ровно в предел включается,
предел+1 байт — нет; кириллический справочник, у которого символов не
больше предела, а байт больше, не включается; подмена
`config.CORE_REFERENCE_MAX_BYTES` в тесте сдвигает границу. Проверяется на
брифе developer и на результате `test_author_answer_component` (ловит:
подсчёт в символах; литерал вместо `config`; исключение ровно предела;
включение предела+1; предел не применён у test_author).

AC-9. Справочник крупнее предела: в брифе вместо компонента строка
«справочник ядра: <размер> байт > <предел> — не включён, решение за
Оператором (сузить настройку проекта или поднять предел)», без указания
читать файл; поднят алерт `incident` источника
`brief.core_reference_oversized` по проекту задачи, текст алерта без
размеров и sha. После возврата размера в предел открытый алерт этого
источника и этого проекта снят; открытый алерт того же источника другого
проекта не снимается и не поднимается. Проверяется на брифе developer и на
результате `test_author_answer_component` (ловит: алерт не поднят / не
снят / поднят или снят по другому проекту; строка предлагает читать файл;
включён справочник крупнее предела; у test_author предел и алерт не
сработали).

AC-10. Размер больше 90% предела и не больше предела — поднят алерт
`warning` источника `brief.core_reference_near_limit` по проекту задачи;
ровно 90% предела — не поднят, 90% + 1 байт — поднят; после возврата
размера к не больше 90% и после подъёма алерта предела (AC-9) открытое
предупреждение снято; тексты без размеров и sha. Проверяется на брифе
developer и на результате `test_author_answer_component` (ловит:
предупреждение не поднято или не снято, в том числе у test_author).

AC-11. При `approve` на `merge_gate` с исходом push `"ok"` шаг после мержа
вызывает `get_reference` с `reason="merge"` и `sha=final_sha` (не головой
ветки задачи и не HEAD до приложений) после `_push_merged_main` и
`_finalize_done_state` и до `cleanup._commit_closing`; при исходе
`"moved"` не вызывается; шаг не создаёт коммитов и не меняет дерево мержа;
для проекта без поля `core_reference` при читаемом `targets.yaml` шаг не
даёт побочных эффектов (ни файла кэша, ни записи журнала сборки, ни
алерта). Фикстура теста содержит коммит карты после мержа (шаг карты
`fsm_postmerge` после приложений), так что `final_sha` отличается от sha
плотницкого merge и от головы ветки задачи; на ней ловится мутация
«пересборка из `sha=merge_sha` вместо `final_sha`» (ловит также: сборка
из головы ветки задачи или HEAD до приложений; вызов до push, до
`_finalize_done_state` или на `"moved"`; побочный эффект у проекта без
поля).

AC-12. `OSError`, `RuntimeError` и `ValueError` из генератора или записи
кэша внутри шага после мержа, а также ошибка записи журнала в обработчике
сбоя шага не срывают мерж: задача в `done`, `cleanup._commit_closing`
исполнен, `approve` завершается без исключения и без `SystemExit`.

AC-13. PLAN.md задачи содержит раздел «## Приложение» с блоком diff к
`targets.yaml`, добавляющим комментарий-пояснение и блок `core_reference`
требования 10 в конец записи `artel` после строки
`full_suite_timeout_sec: 1500`, без правки шапки файла;
`guard.plan_appendices(PLAN)` возвращает ровно одно приложение с путём
`targets.yaml`. Разметка в планке: `# AC-13: skip — проверяется ревью и
guard`.

AC-14. `docs/codebase-map.md` на голове ветки совпадает с выводом
`python3 scripts/codebase_map.py`.

## Меняемое поведение

Нет: ожидания существующих тестовых методов не меняются. При записи
проекта без поля `core_reference` прежними остаются, в частности,
`tests/test_brief.py::DeveloperBriefTest::test_assembles_three_components_and_journals_their_hashes`
(ровно 3 записи «бриф: компонент»),
`tests/test_brief.py::ReturnReasonComponentTest::test_test_author_brief_unchanged_on_the_approve_out_of_spec_gate`
(`assertIsNone`), записи «бриф: компонент» ревьюера в
`tests/test_review_package.py` и `tests/test_advance_refusal_history.py`
(песочница `TmpRootTest` подменяет `config.TARGETS` записью без поля).
Проверка: полный набор `tests/` зелёный без приложения и с ним (CI ветки
накладывает приложение до тестов; `tests/test_multitarget.py::TargetsFileTest::test_repository_file_is_valid`
читает настоящий `targets.yaml` — с приложением проходит при К-3а в main).

## Оценка объёма и деление

Сработавшие сигналы: зоны — 5 путей (`orchestrator/brief.py`,
`orchestrator/fsm_merge_gate.py`, `orchestrator/config.py`, `tests/`,
`docs/codebase-map.md`); число критериев приёмки ≥ 10 (14); `budget_usd` ≥
$30 (45).

Обоснование монолита (из ТЗ): бриф, предел и шаг после мержа — тонкие
потребители одного интерфейса К-3а (`reference_cache.get_reference`);
предел без компонента брифа проверять не на чем, а приложение к
`targets.yaml` без потребителей не имеет смысла (поле включает механизм,
которого нет). `config.py` несёт только константу предела, `tests/` и
карта — сопровождение тех же правок. Решение принимает Оператор на гейте
SPEC.

## Не входит

- Генератор `scripts/core_reference.py`, проверка поля `core_reference` и
  кэш `orchestrator/reference_cache.py` — задача К-3а
  (01M4S24963R9H18AN2XDP6R15B).
- Справочник для reviewer (работает от ревью-пакета; чтения не
  замерялись), analyst и spec_auditor.
- `scripts/guard.py` в настройке артели (не помещается в предел).
- Сокращение проекции карты; изменение `config.CONTEXT_FILE_MAX_BYTES` и
  деления брифа на части (`CONTEXT_PART_MAX_BYTES`).
- Команда пересборки кэша; проверка `doctor` настройки; алерт «поле
  отсутствует».
- Настройка для sled и других проектов (Оператор, `doc-commit`).
- Карточки знаний (К-4а, К-4б; `orchestrator/knowledge_cards.py`).
- Правка путей только для чтения из ТЗ: `targets.yaml` (только
  приложением PLAN), `scripts/core_reference.py`,
  `orchestrator/reference_cache.py`, `orchestrator/targets.py`,
  `orchestrator/role_prompt.py`, `orchestrator/review.py`,
  `orchestrator/fsm_postmerge.py`, `orchestrator/alerts.py`,
  `orchestrator/context_package.py`, `orchestrator/runner.py`,
  `orchestrator/store.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`,
  `orchestrator/repo_context.py`, `orchestrator/yamlmini.py`,
  `scripts/guard.py`, `scripts/plan_appendix_ci.py`,
  `scripts/codebase_map.py`, `tests/test_invariants.py`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `skills/`, `templates/`, `CLAUDE.md`,
  `roles.yaml`, `.github/`, файл кэша
  `.artel/projects/<проект>/knowledge/derived/core-reference.md`.
- Полный зелёный набор `tests/`, зелёный CI ветки, неизменность
  защищённых путей и непревышение бюджета — их держит пульт.

## Материалы

- ТЗ: `tasks/01M4S24EBVB72B8WYJ3JY96Y0E/TZ.md` (факты сверены на origin/main
  b13c9e87).
- Образцы: `brief._handle_map_size_alert` (~630),
  `brief.MAP_OVERSIZED_ALERT_SOURCE` (~94), `map_note` (~718–731),
  `fsm_postmerge._regenerate_and_commit_map` (~76),
  `fsm_merge_gate._apply_plan_appendices` (~988).
- Включение: код и приложение начинают работать после `pin-update`;
  первая запись «справочник ядра: построен» появится у первой задачи после
  него, не в журнале мержа К-3б.
- Пересечения: К-2а (01M4RZBDFSHNESSBQREH5MKY9B) правит `brief.py`; К-2б
  (01M4RZBPG6EXM74MTBPTEGW2D4) — `brief.py` и `fsm_merge_gate.py`;
  приложение К-4а к `targets.yaml` накладывается с этим в любом порядке;
  01M4C200DKW7GXHBH8RAJVH9HD при более раннем мерже — конфликт в
  `developer_brief` на подтяжке чинит роль.
- Принятый остаточный риск: процесс роли может переписать файл кэша; его
  текст роль получает как данные внутри границы.
