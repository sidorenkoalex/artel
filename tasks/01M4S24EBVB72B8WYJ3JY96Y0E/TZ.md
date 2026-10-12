---
task: 01M4S24EBVB72B8WYJ3JY96Y0E
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Справочник ядра в брифе и пересборка после мержа

# ТЗ-К3б: Справочник ядра — бриф, предел размера, шаг после мержа, настройка артели

Источник: решение Оператора 12.10.2026 — план обогащения ролей знаниями,
задача 3 из 4 (полный вариант, решение 13.10); часть «б» из двух. Часть
«а» (ТЗ К-3а) даёт генератор `scripts/core_reference.py`, проверку поля
`core_reference` записи проекта и кэш с интерфейсом
`reference_cache.get_reference(conn, task_id, *, reason, sha=None)` →
`text`, `note`, `state` (`off`/`fresh`/`cached`/`unverified`/`absent`),
вместе с журналом сборки и алертами сбоев. Эта часть — потребители:
бриф developer и test_author, предел размера, сборка после мержа и
настройка артели приложением к `targets.yaml`. Цель — короткий ответ «как
пользоваться» порядка 5–10 тыс. токенов на шаг.

Заводить после К-3а: id К-3а подставить вместо 01M4S24963R9H18AN2XDP6R15B в строке
порядка до `new --tz`.

Факты (origin/main b13c9e87; номера строк сверены на нём):
- Бриф: `orchestrator/brief.py::developer_brief` (~677) собирает SPEC,
  проекцию карты (73 029 байт), `CLAUDE.md`, PLAN/REVIEW, ANSWER через
  `_manifest_component` (~386: запись «бриф: компонент» с sha256 в журнал,
  опись путь/размер/sha256, граница недоверенных данных, пропуск только
  крупнее `config.CONTEXT_FILE_MAX_BYTES` = 131 072, ~519). Пометка
  стухлости карты идёт ПЕРЕД компонентом и в хэшируемый текст не входит
  (`map_note`, ~718–731). `test_author_answer_component` (~1017) — добавка
  брифа test_author (причина возврата и ANSWER; без них — `None`).
  Reviewer получает ревью-пакет (`orchestrator/review.py`), не бриф.
- Предел с алертом — образец `brief._handle_map_size_alert` (~630):
  источник `brief.codebase_map_oversized` (~94), вид `incident`,
  автоматическое снятие (`alerts.auto_ack`), когда размер снова в
  пределе. Виды алертов — `alerts.KINDS` (~73), есть `warning`. Дедуп
  `alerts.raise_alert` (~93) — по точному тексту.
- Мерж: `fsm_merge_gate._cmd_approve_merge_gate` (~1240):
  `_publish_merge_artifacts` (~1067, внутри — `final_sha` ~1088 и
  `_drop_scratch_worktree` ~1089; объекты коммита остаются в клоне
  проекта) → `_push_merged_main` (~1112: `"ok"`, `"moved"` — повтор
  мержа, иначе `sys.exit`) → `_finalize_done_state` (~1150), строки
  ~1328–1331. Образец шага после мержа —
  `fsm_postmerge._regenerate_and_commit_map` (~76, ловит только
  `OSError`). После `_finalize_done_state` (задача `done`, lease снят)
  идут `cleanup._commit_closing` (~1332), уборка и ожидание CI `main`.
- Приложение к `targets.yaml` пишет в PLAN роль developer разделом «##
  Приложение» с блоком diff (`guard.plan_appendices`); на `approve`
  merge_gate его накладывает пульт (`fsm_merge_gate._apply_plan_appendices`
  ~988) отдельным коммитом после плотницкого merge и до шага карты;
  неприменимое к подтянутому `main` пульт возвращает в `in_dev`
  (`_return_inapplicable_appendix` ~857), и роль перебирает diff по
  свежему `targets.yaml`. CI ветки накладывает приложение до тестов
  (`scripts/plan_appendix_ci.py`). Ни один гейт не замечает ОТСУТСТВИЯ
  приложения — без него механизм для артели молча выключен.
- Приложения К-3б и К-4 правят одну запись `artel` файла `targets.yaml`
  (защищённый путь): блок `core_reference` дописывается в конец файла
  (после `full_suite_timeout_sec: 1500`, стр. 44 — файл ею кончается),
  правка К-4 — в `no_paths` (стр. 33), шапку (стр. 5–12) и поле
  `knowledge`; текстового пересечения нет, пока ни одна из задач не
  дописывает в конец файла. Дописывать именно в конец, а не внутрь
  `test_profile`, требуют и тесты, правящие настоящий файл регулярным
  выражением по `full_suite_timeout_sec`
  (`tests/test_01m48wt5x7zc7332drh85vy19d_profile_timeout.py`,
  `tests/test_full_suite_profile_timeout.py`). Блок из «Приложением»
  разбирается `yamlmini.mapping` и ложится последним ключом записи.
- Включение: код К-3б и приложение начинают работать после `pin-update`
  (пульт, мержащий К-3б, исполняет прежний код), поэтому первая запись
  «справочник ядра: построен» артели появится у первой задачи после
  `pin-update`, а не в журнале мержа К-3б.
- Замер (прототип вне репозитория, b13c9e87): справочник на настройке
  артели из «Приложением» — около 26,7–26,8 КБ (около 7 тыс. токенов), с
  `scripts/guard.py` — 34 280 байт. Запас до предела 32 768 — около 18%,
  до порога предупреждения 90% (29 491 байт) — около 2,7 КБ: ранний
  сигнал ожидаем и принят Оператором (13.10); предел остаётся 32 768. Деление брифа на части
  (`CONTEXT_PART_MAX_BYTES` = 65 536) сохраняется; промпт идёт на stdin.
- test_author: замера чтений у test_author нет; справочник включён ему
  решением Оператора (полный вариант) как дешёвая добавка — его
  `tests/sandbox.py` и `orchestrator/store.py` нужны при написании
  тестов. Основание проверяется метрикой К-1 после внедрения.
- Тесты, чьи ожидания при поле нет обязаны остаться прежними:
  `tests/test_brief.py::DeveloperBriefTest::test_assembles_three_components_and_journals_their_hashes`
  (ровно 3 записи «бриф: компонент»),
  `tests/test_brief.py::ReturnReasonComponentTest::test_test_author_brief_unchanged_on_the_approve_out_of_spec_gate`
  (`assertIsNone`), записи «бриф: компонент» ревьюера в
  `tests/test_review_package.py`, `tests/test_advance_refusal_history.py`.
  Песочница (`TmpRootTest`) подменяет `config.TARGETS` записью без поля.
  `tests/test_multitarget.py::TargetsFileTest::test_repository_file_is_valid`
  читает настоящий `targets.yaml` — с приложением пройдёт при К-3а в main.
- Пересечения: К-2а (01M4RZBDFSHNESSBQREH5MKY9B) правит `brief.py`;
  К-2б (01M4RZBPG6EXM74MTBPTEGW2D4) — `brief.py` и `fsm_merge_gate.py`.
  01M4R4JDG8RH53ZNWM0XF90CFJ, правившая `brief.py`, уже в main.
  ТЗ К-4а/К-4б (01M4S0JVB85W9TY1ESGNBH97FP, 01M4S0K2MJRMVMQWKATAME3RHR)
  заводят `orchestrator/knowledge_cards.py`; К-3 его не импортирует и не
  трогает. Приложение К-4а к `targets.yaml` (строка шапки, `no_paths`,
  поле `knowledge` после `merge_gate`) и приложение этой задачи
  накладываются `git apply` в любом порядке с одинаковым итогом
  (проверено). 01M4C200DKW7GXHBH8RAJVH9HD (черновик ТЗ) тоже правит `brief.py`: строки
  порядка на неё нет — если она смержится раньше, конфликт в
  `developer_brief` на подтяжке чинит роль.

Требуется:
1. Бриф developer: компонент справочника из
   `reference_cache.get_reference(conn, task_id, reason="brief")` — сразу
   после проекции карты и до конвенций (`CLAUDE.md`). Бриф test_author:
   тот же компонент после причины возврата и ANSWER; `note` без
   компонента (`absent`) тоже делает результат
   `test_author_answer_component` не `None`; `off` — `None`, как прежде.
   Опись (`_manifest_component`) у test_author — осознанное расширение:
   новая запись «бриф: компонент» появляется только при справочнике. Reviewer, analyst и spec_auditor справочник не получают.
   `state == "off"` — бриф байт в байт прежний (ни компонента, ни
   пометки, ни записи журнала).
2. Оформление компонента — `_manifest_component` у обеих ролей: метка с
   относительным путём кэша
   (`.artel/projects/<проект>/knowledge/derived/core-reference.md`, без
   домашнего каталога), размер и sha256 в описи, запись «бриф: компонент»
   в журнал, граница недоверенных данных. `note` (не сверен, отсутствует,
   сбой) идёт ПЕРЕД компонентом и в хэшируемый текст не входит — тем же
   приёмом, что `map_note`. `state == "absent"` — только `note`, без
   компонента.
3. Предел: `config.CORE_REFERENCE_MAX_BYTES = 32_768` — в байтах UTF-8
   (запас около 18% над замером на b13c9e87). Справочник крупнее — в бриф не идёт;
   вместо него строка «справочник ядра: <размер> байт > <предел> — не
   включён, решение за Оператором (сузить настройку проекта или поднять
   предел)» без указания «читай адресно» (файл может перезаписать сборка
   соседней задачи); алерт `incident` источника
   `brief.core_reference_oversized` по проекту задачи. Размер снова в
   пределе — открытый алерт этого источника и проекта снимается
   автоматически (образец `_handle_map_size_alert`). Тексты алертов без
   размеров и sha.
4. Предупреждение до предела: размер больше 90% предела (и не больше
   предела) — алерт `warning` источника `brief.core_reference_near_limit`
   по проекту задачи; снимается автоматически, когда размер не больше 90%
   или когда поднят алерт предела п. 3.
5. Шаг после мержа в `_cmd_approve_merge_gate`: сразу ПОСЛЕ
   `_finalize_done_state` (задача уже `done`, lease снят, `main` обновлён
   успешным push) и до `cleanup._commit_closing` —
   `get_reference(conn, task_id, reason="merge", sha=final_sha)` для
   проекта задачи (у проекта без поля — `off`, ничего не делается). Шаг
   ничего не коммитит и дерево мержа не меняет; на `"moved"` не
   вызывается. Весь шаг, включая запись журнала и алерта в обработчике
   сбоя, исполняется под `try/except Exception`; помощников, завершающих
   процесс (`sys.exit`, например `brief._main_branch_text`), шаг не
   вызывает. Сбой, зависание или остановка процесса в шаге не оставляют
   задачу в `merge_gate` при обновлённом `main`. Срок — общий срок сборки
   К-3а (60 с на оба вызова git и разбор).
6. Приложение к PLAN к `targets.yaml` (см. «Приложением»): PLAN.md задачи
   содержит раздел «## Приложение» с блоком diff, добавляющим блок
   `core_reference` в конец записи `artel` после строки
   `full_suite_timeout_sec: 1500`; `guard.plan_appendices(PLAN)`
   возвращает ровно одно приложение с путём `targets.yaml`. Критерий
   проверяется ревью и guard, не `tests/` (разметка `# AC-n: skip —
   проверяется ревью и guard`). Проверка Оператора после мержа: в
   журнале мержа есть «приложения применены: targets.yaml»; после
   `pin-update` первый бриф developer или test_author артели несёт
   компонент справочника и запись «справочник ядра: построен»; нет —
   правка `targets.yaml` Оператором (`doc-commit`). Отдельного алерта
   «поле отсутствует» нет: механизм не знает имён проектов.
7. Тесты в `tests/` с заявками «Ловит мутацию», на временном
   `targets.yaml` и области проектов песочницы (настоящие `targets.yaml`
   и `.artel/projects` не читаются и не пишутся):
   - компонент не дошёл до брифа developer или test_author, дошёл до
     reviewer/analyst/spec_auditor; стоит не после проекции карты; нет
     записи «бриф: компонент»; при `off` бриф изменился;
     `test_author_answer_component` вернул `None` при справочнике;
   - `note` внутри хэшируемого текста (опись расходится с текстом
     компонента); `absent` дал пустой компонент вместо пометки;
   - предел считан в символах, а не в байтах (кириллица); справочник
     крупнее предела включён; алерт предела не поднят, не снят после
     возврата в предел, поднят или снят по другому проекту; строка
     пропуска предлагает читать файл; предупреждение 90% не поднято или
     не снято; справочник ровно в предел исключён или предел+1 байт
     включён; предупреждение поднято на ровно 90% или не поднято на 90%+1
     байт; предел взят литералом, а не из `config`;
   - `unverified`: пометка не перед компонентом или внутри хэшируемого
     текста; `fresh`/`cached` дали пометку; у test_author компонент стоит
     до ANSWER; у developer — не между проекцией карты и `CLAUDE.md`;
   - шаг после мержа: собран из головы ветки задачи или HEAD до
     приложений, а не из `final_sha`; вызван до push, до
     `_finalize_done_state` или на `"moved"`;
     `OSError`/`RuntimeError`/`ValueError` из генератора или записи кэша
     сорвали мерж; ошибка записи журнала в обработчике сорвала мерж;
     вызван для проекта без поля с побочным эффектом.
   Существующие тесты не ослабляются; ожидания тестов, названных в
   «Фактах», при поле нет не меняются. SPEC содержит раздел «Меняемое
   поведение» с явным «нет» и проверкой «полный набор `tests/` зелёный
   без приложения и с ним (CI ветки накладывает приложение до тестов)».
8. `docs/codebase-map.md` обновляется в той же задаче.

Приложением: targets.yaml — в конец записи `artel`, после строки
`full_suite_timeout_sec: 1500`, с комментарием-пояснением прямо над
блоком, шапку файла не трогать; блок ниже, отступы буквальные
(`core_reference:` — 4 пробела, подполя — 6).

```yaml
    core_reference:
      modules: [orchestrator/store.py, orchestrator/config.py, tests/sandbox.py, orchestrator/fsm.py, orchestrator/runner.py, orchestrator/gitcmd.py]
      constants_module: orchestrator/config.py
      constants: [PROTECTED_PATHS, COMMON_ZONES, STATE_ROLE, DEFAULT_TARGET, PROJECT_DIRS, MAIN_BRANCH, ROOT, TASKS, PROJECTS, TARGETS, DB, LOGS]
```

Матрица неослабления: проверки, гейты, лимиты и тесты не меняются;
`CONTEXT_FILE_MAX_BYTES` не трогается (новый предел ниже него); проект
без поля работает байт в байт как сейчас, кроме случая нечитаемого
`targets.yaml` (пометка и алерт, бриф и мерж не останавливаются);
справочник идёт роли внутри границы недоверенных данных; шаг после мержа
стоит после push и перевода задачи в `done` и не может сорвать мерж,
push или закрытие; бриф
developer и test_author растёт на ~27 КБ (около 7 тыс. токенов) — цена,
не ослабление, потолок держит п. 3. Принятый остаточный риск: процесс
роли технически может переписать файл кэша; его текст роль получает как
данные внутри границы.

Оценка объёма: сигнал «зоны» срабатывает (5 путей); обоснование монолита —
бриф, предел и шаг после мержа — тонкие потребители одного интерфейса
К-3а, приложение без них не имеет смысла; решение принимает Оператор на
гейте SPEC.

Зоны: orchestrator/brief.py, orchestrator/fsm_merge_gate.py,
orchestrator/config.py, tests/, docs/codebase-map.md.

Только чтение (не менять): targets.yaml (только приложением),
scripts/core_reference.py, orchestrator/reference_cache.py,
orchestrator/targets.py, orchestrator/knowledge_cards.py,
orchestrator/role_prompt.py, orchestrator/review.py,
orchestrator/fsm_postmerge.py, orchestrator/alerts.py,
orchestrator/context_package.py, orchestrator/runner.py,
orchestrator/store.py, orchestrator/fsm.py, orchestrator/gitcmd.py,
orchestrator/repo_context.py, orchestrator/yamlmini.py,
scripts/guard.py, scripts/plan_appendix_ci.py, scripts/codebase_map.py,
tests/test_invariants.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
skills/, templates/, CLAUDE.md, roles.yaml, .github/,
.artel/projects/<проект>/knowledge/derived/core-reference.md.

Не входит: генератор, проверка поля и кэш (К-3а); справочник для
reviewer (работает от ревью-пакета; чтения не замерялись), analyst и
spec_auditor; `scripts/guard.py` в настройке артели (не помещается в
предел); сокращение проекции карты; команда пересборки кэша; проверка
`doctor` настройки; настройка для sled и других проектов (Оператор,
doc-commit); карточки знаний (К-4а, К-4б); полный зелёный набор `tests/`, CI
ветки, неизменность защищённых путей и бюджет — их держит пульт.

Порядок: после 01M4S24963R9H18AN2XDP6R15B, 01M4RZBDFSHNESSBQREH5MKY9B, 01M4RZBPG6EXM74MTBPTEGW2D4.

Рамка: $45.

Набор моделей: по умолчанию.
