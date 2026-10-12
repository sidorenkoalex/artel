---
task: 01M4RZBDFSHNESSBQREH5MKY9B
type: spec
author_role: analyst
status: draft
schema_version: 5
zones: orchestrator/brief.py, orchestrator/role_prompt.py, tests/, docs/codebase-map.md
merge_after: 01M4R4JDG8RH53ZNWM0XF90CFJ
budget_usd: 40
---

# SPEC: Бриф: шаблон артефакта роли целиком

## Контекст
ТЗ К-2а (решение Оператора 12.10.2026, план обогащения ролей знаниями,
задача 2 из 4, часть А). Шаблон артефакта, который роль обязана
заполнить, сейчас в бриф не кладётся: миссия велит роли читать его
самой (`orchestrator/role_prompt.py:44`, `:49` — analyst, `:101` —
developer, `:189–190` — spec_auditor), и `templates/PLAN.md` читают 70%
первых шагов developer (замер 12.10 по 392 журналам) — отдельным
вызовом на каждом шаге. Исключение — reviewer: форма `templates/REVIEW.md`
уже в ревью-пакете (`orchestrator/review.py`). Задача кладёт шаблон
артефакта в бриф роли целиком, читая его с `main` пульта, как скилы
(`brief.skills_text`, `orchestrator/brief.py:432`), и честно помечает
неудачу чтения.

## Требования
1. Бриф роли несёт целиком шаблон артефакта, который роль выпускает:
   analyst — `templates/SPEC.md` и `templates/QUESTIONS.md`; developer —
   `templates/PLAN.md`; spec_auditor — `templates/SPEC-AUDIT.md`.
   reviewer не меняется (форма REVIEW уже в ревью-пакете, второй копии
   нет); test_author шаблона не получает. Соответствие «роль → шаблоны»
   — одна таблица в `orchestrator/brief.py`.
2. Шаблон добавляется внутри функций брифа (`brief.analyst_map_component`,
   `brief.developer_brief`, `brief.spec_auditor_brief`), не в
   `orchestrator/role_prompt.py`: тесты, подменяющие эти функции, не
   меняются. Компоненты шаблонов идут после уже существующих компонентов
   брифа роли — первая запись журнала «бриф: компонент» остаётся прежней
   (у analyst — карта, у developer и spec_auditor — первый компонент
   роли).
3. Шаблон читается `gitcmd.show(config.MAIN_BRANCH, "templates/<имя>",
   repo=config.ROOT)` напрямую — не через `brief._main_branch_text`, не с
   диска и не с ветки задачи. Оформление — как у соседних компонентов
   роли: developer и spec_auditor — `_manifest_component` (опись и потолок
   файла брифа действуют на шаблон так же, как на остальные компоненты),
   analyst — `_journal_component`; метка `templates/<имя>`, тело в границе
   `wrap_boundary` с id запуска, sha256 исходного текста шаблона (до
   обёртки) — в журнал «бриф: компонент».
4. Шаблон не прочитан (git не ответил, файла нет) — бриф собирается,
   вместо компонента стоит пометка вне границы «шаблон templates/<имя> не
   прочитан: <причина> — прочитай его сам», и в журнал шага пишется
   запись от имени роли шага с действием «бриф: шаблон не прочитан». Ни
   падения сборки брифа, ни молчаливого пропуска.
5. Миссии analyst, developer, spec_auditor (`orchestrator/role_prompt.py`)
   говорят, что шаблон — в БРИФЕ РОЛИ ниже, и велят читать файл
   `templates/<имя>` с диска только если вместо шаблона в брифе стоит
   пометка «шаблон … не прочитан». Имя шаблона в миссии остаётся.
6. В `tests/` — тесты с заявками «Ловит мутацию» на каждую мутацию
   перечня критерия AC-9.
7. Ожидания существующих тестов, меняемые требованиями 1–4, перечислены
   в разделе «Меняемое поведение»; ослабления утверждений нет.
8. `docs/codebase-map.md` обновляется в той же задаче.

## Критерии приёмки

AC-1. Бриф developer (`brief.developer_brief`) содержит компонент с
меткой `templates/PLAN.md`: заголовок описи (размер, sha256), тело —
текст `templates/PLAN.md` с головы `main` пульта целиком внутри пары
граничных маркеров с id запуска; в журнале шага есть запись актора
`developer` с действием «бриф: компонент» и деталью
`templates/PLAN.md: sha256=<sha256 исходного текста шаблона до обёртки>`.

AC-2. Бриф analyst (`brief.analyst_map_component`) содержит оба
компонента — `templates/SPEC.md` и `templates/QUESTIONS.md` — с текстом
с головы `main` внутри границы и по записи журнала «бриф: компонент»
актора `analyst` на каждый с sha256 исходного текста; компонента
`templates/PLAN.md` в брифе analyst нет.

AC-3. Бриф spec_auditor (`brief.spec_auditor_brief`) содержит компонент
`templates/SPEC-AUDIT.md` с описью (размер, sha256) и телом с головы
`main` внутри границы, и запись журнала «бриф: компонент» актора
`spec_auditor` с sha256 исходного текста.

AC-4. Ревью-пакет reviewer и добавка брифа test_author
(`brief.test_author_answer_component`) не содержат ни одного компонента
шаблона `templates/<имя>` и не дают записей журнала с меткой
`templates/…`; форма `templates/REVIEW.md` в ревью-пакете — одна копия,
как до задачи.

AC-5. В песочнице, где текст `templates/<имя>` на `main` пульта
отличается от текста на диске `config.ROOT` и на ветке задачи, бриф
analyst, developer и spec_auditor несёт текст `main`, а sha256 в журнале
равен sha256 текста `main`.

AC-6. Компоненты шаблонов стоят в брифе после всех уже существующих
компонентов роли, и первая запись журнала «бриф: компонент» шага
прежняя: у analyst — карта (`MAP_PROJECTION_LABEL`), у developer и
spec_auditor — тот же первый компонент роли, что без шаблонов.

AC-7. Когда `gitcmd.show` не вернул шаблон (git не ответил или файла на
`main` нет): сборка брифа analyst, developer и spec_auditor завершается
без исключения и без выхода процесса; в брифе вне граничных маркеров
стоит строка «шаблон templates/<имя> не прочитан: <причина> — прочитай
его сам»; в журнале шага есть запись с актором, равным роли шага, и
действием «бриф: шаблон не прочитан» (не «бриф: компонент»). Для analyst
это выполняется для каждого из двух шаблонов отдельно.

AC-8. Миссии analyst, developer и spec_auditor
(`role_prompt.mission_brief_package`) называют шаблон по имени
(`templates/SPEC.md` и `templates/QUESTIONS.md`, `templates/PLAN.md`,
`templates/SPEC-AUDIT.md`), говорят, что он — в БРИФЕ РОЛИ, и велят
читать файл `templates/<имя>` с диска только при пометке «шаблон … не
прочитан» в брифе; безусловного указания читать шаблон с диска в них
нет.

AC-9. В `tests/` есть тесты с заявками «Ловит мутацию» на каждую из
мутаций: developer не получил шаблон PLAN; analyst получил PLAN вместо
SPEC и QUESTIONS; spec_auditor не получил SPEC-AUDIT; reviewer или
test_author получили шаблон (вторая копия формы REVIEW); шаблон прочитан
с диска или ветки задачи, а не с `main`; компонент шаблона без границы
или без записи журнала, либо sha256 записи не равен sha256 исходного
текста шаблона до обёртки; при неудаче чтения компонент тихо пропал (нет
пометки или записи журнала) либо сборка брифа упала; миссия developer
велит читать `templates/PLAN.md` безусловно, без оговорки о пометке «не
прочитан»; компонент шаблона поставлен перед существующими компонентами
брифа (первая запись журнала «бриф: компонент» перестала быть прежней);
analyst получил только один из двух шаблонов; неудача чтения записана не
от имени роли шага либо общим действием «бриф: компонент» вместо «бриф:
шаблон не прочитан».

## Меняемое поведение
Песочницы тестов отвечают на `gitcmd.show` диском `config.ROOT`
(`tests/sandbox.py` `fake_git`, `disk_backed_show`), `templates/` там
обычно нет — брифы получают записи «бриф: шаблон не прочитан», и
`journal_details` (`tests/test_brief.py`, считает все записи актора)
видит их. Перечень сверен прогоном файлов `tests/`, достающих до
сборщиков брифа, с имитацией требований 1–4 (см. «Материалы»).

- `tests/test_brief.py::DeveloperBriefTest::test_assembles_three_components_and_journals_their_hashes`: `3` → `4` (требование 4)
- `tests/test_brief.py::AnalystMapComponentTest::test_adds_only_the_map_and_journals_one_hash`: `1` → `3` (требование 4)

## Оценка объёма и деление
Сработавший сигнал: `budget_usd` ≥ $30 (ставка $40 — класс «до 10
критериев и до 4 файлов зоны» калибровки, рамка ТЗ «$40»).

Материал для решения Оператора — обоснование монолита. Механика одна:
таблица «роль → шаблоны», чтение с `main` и пометка неудачи в
`orchestrator/brief.py`; миссии в `orchestrator/role_prompt.py`
опираются на неё («шаблон в брифе, читай с диска только при пометке»).
Миссия без шаблона в брифе велела бы роли не читать шаблон, которого у
неё нет; шаблон без смены миссии — дублирующее чтение, то есть
промежуточное состояние обесценивает задачу, а смена ожиданий
`tests/test_brief.py` — прямое следствие той же правки `brief.py`.
Деление по ролям (analyst / developer / spec_auditor) резало бы зону
`orchestrator/brief.py` и `orchestrator/role_prompt.py` поперёк: каждая
часть трогает обе.

## Не входит
- Записка следующему шагу и раздел «Чего не хватило» — часть Б (ТЗ
  К-2б).
- Формулировки «по templates/…» в `skills/spec-authoring.md` и других
  скилах (защищённый путь, по смыслу не расходятся).
- Шаблон для test_author.
- Изменение ревью-пакета и источника формы REVIEW
  (`orchestrator/review.py` — только чтение).
- Изменение `templates/`, `skills/`, `scripts/guard.py`,
  `scripts/codebase_map.py`, `orchestrator/runner.py`,
  `orchestrator/context_package.py`, `orchestrator/gitcmd.py`,
  `orchestrator/config.py`, `tests/test_invariants.py`, `**/conftest.py`,
  `pyproject.toml` и прочих путей «Только чтение» ТЗ.
- Пять тестов, зовущих `mission_brief_package(None, …)` с подменой
  сборщиков брифа (`tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`,
  `tests/test_docs_dir_layout.py::MissionNamesDocsDirTest`,
  `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`,
  `tests/test_role_prompt_test_author_mission.py`,
  `tests/test_long_lived_manifest.py::RolePromptTest`), не меняются.
- Полный зелёный набор `tests/`, зелёный CI ветки (в том числе джоб
  свежести карты), неизменность защищённых путей и непревышение бюджета
  — их держит пульт.

## Материалы
- ТЗ: `tasks/01M4RZBDFSHNESSBQREH5MKY9B/TZ.md`.
- Код: `orchestrator/brief.py:374` (`_journal_component`), `:386`
  (`_manifest_component`), `:410` (`_main_branch_text`, `sys.exit` при
  неудаче — для шаблона не годится), `:432` (`skills_text`), `:677`
  (`developer_brief`), `:762` (`spec_auditor_brief`), `:977`
  (`analyst_map_component`), `:1017` (`test_author_answer_component`);
  `orchestrator/role_prompt.py:43–49`, `:101`, `:189–190`.
- Задача 01M4R4JDG8RH53ZNWM0XF90CFJ правила ту же `spec_auditor_brief`
  (в `main` на 91a2b0d7) — поле `merge_after` по строке ТЗ «Порядок:
  после …». Задача 01M4C200DKW7GXHBH8RAJVH9HD тоже заявила
  `orchestrator/brief.py`; решение Оператора 12.10 — её не ждать.
- Замер перечня «Меняемого поведения» (13.10.2026, ветка задачи на
  91a2b0d7): полный прогон внутри шага роли запрещён сторожем роли,
  поэтому прогнаны адресно 74 файла `tests/`, достающих до сборщиков
  брифа (вызов `analyst_map_component`/`developer_brief`/
  `spec_auditor_brief`/`mission_brief_package`, запись «бриф: компонент»
  или запуск шага `cmd_run`/`cmd_auto`/`run_agent_once`). Без изменений —
  1557 passed. С имитацией требований 1–4 (подмена трёх сборщиков
  pytest-плагином в памяти, код не менялся) — RESULT_PLACEHOLDER.
