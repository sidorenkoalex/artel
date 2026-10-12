---
task: 01M4RZBDFSHNESSBQREH5MKY9B
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Бриф: шаблон артефакта роли целиком

# ТЗ К-2а: Бриф — шаблон артефакта роли целиком

Источник: решение Оператора 12.10.2026 — план обогащения ролей знаниями,
задача 2 из 4, часть А (часть Б — записка шага, отдельное ТЗ К-2б).
Данные: `templates/PLAN.md` читают 70% первых шагов developer (замер
12.10 по 392 журналам) — шаблон, который роль обязана заполнить, она
каждый раз читает отдельным вызовом.

Факты (origin/main 3142b93b; до ddcf33b1 менялся только docs/backlog.md):
- Бриф по ролям (`role_prompt.mission_brief_package`, `role_prompt.py`
  ~13–147): analyst — `brief.analyst_map_component` (`brief.py` ~913),
  test_author — `brief.test_author_answer_component` (~953), developer —
  `brief.developer_brief` (~666, опись и деление на части
  `context_package.discipline`), spec_auditor — `brief.spec_auditor_brief`
  (~751), reviewer — брифа нет, только ревью-пакет.
- Шаблоны в бриф не кладутся; миссия велит роли читать их самой:
  analyst — «по templates/SPEC.md», «по templates/QUESTIONS.md»
  (`role_prompt.py` ~44, ~49), developer — «по templates/PLAN.md» (~101),
  spec_auditor — «по templates/SPEC-AUDIT.md» (~189–190). reviewer —
  исключение: форма `templates/REVIEW.md` уже в ревью-пакете (`review.py`
  ~773, с кодовой ветки). У test_author шаблона нет. Размеры на main:
  SPEC.md 11 142 байт, QUESTIONS.md 2 944, PLAN.md 3 537, SPEC-AUDIT.md
  3 125; потолок файла брифа `config.CONTEXT_FILE_MAX_BYTES` = 131 072
  (`config.py` ~519).
- Правила системы бриф читает с головы `main` пульта: `skills_text`
  (~421) через `gitcmd.show(config.MAIN_BRANCH, …, repo=config.ROOT)`,
  при неудаче возвращает `(None, причина)`; `_main_branch_text` (~399)
  при неудаче завершает процесс (`sys.exit`) — для шаблона не годится.
- Оформление компонентов: `_journal_component` (~363) и
  `_manifest_component` (~375) — sha256 исходного текста в журнал
  «бриф: компонент», тело в границе `wrap_boundary` (~126) с id запуска.
- Тесты с точными счётчиками записей журнала брифа:
  `tests/test_brief.py::DeveloperBriefTest::test_assembles_three_
  components_and_journals_their_hashes` (`assertEqual(len(details), 3)`,
  ~221) и `AnalystMapComponentTest::test_adds_only_the_map_and_journals_
  one_hash` (`assertEqual(len(details), 1)` и `details[0]` — карта,
  ~263–264); `journal_details` считает все записи актора (~78). Песочницы
  тестов отвечают на `gitcmd.show` диском `config.ROOT` (`tests/sandbox.py`
  `fake_git` ~1361, `disk_backed_show` ~794); `templates/` там обычно нет.
- Пять тестов зовут `mission_brief_package(None, …)` с подменой
  сборщиков брифа (`tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py`,
  `tests/test_docs_dir_layout.py::MissionNamesDocsDirTest`,
  `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` ~1438,
  `tests/test_role_prompt_test_author_mission.py`,
  `tests/test_long_lived_manifest.py::RolePromptTest::test_test_author_
  and_developer_missions_name_own_prefix` ~381): чтение шаблона вне
  подменённых функций `brief` уронило бы их на соединении `None`. Шаблон
  читается внутри функций брифа, поэтому они не меняются.
- Задача 01M4R4JDG8RH53ZNWM0XF90CFJ (в приёмке) правит ту же
  `spec_auditor_brief` в `brief.py`. Задача 01M4C200DKW7GXHBH8RAJVH9HD
  (spec_writing, без шагов) тоже заявила `brief.py`; решение Оператора
  12.10 — её не ждать, порядок задаёт она сама при продвижении.

Требуется:
1. Бриф роли несёт целиком шаблон артефакта, который роль выпускает:
   analyst — `templates/SPEC.md` и `templates/QUESTIONS.md`; developer —
   `templates/PLAN.md`; spec_auditor — `templates/SPEC-AUDIT.md`. reviewer
   не меняется (форма уже в ревью-пакете, второй копии нет); test_author
   шаблона не получает. Соответствие «роль → шаблоны» — одна таблица в
   `brief.py`.
2. Шаблон добавляется внутри функций брифа (`analyst_map_component`,
   `developer_brief`, `spec_auditor_brief`), не в `role_prompt.py`:
   тесты, подменяющие эти функции, не меняются. Компоненты шаблонов идут
   после уже существующих компонентов брифа роли (первая запись журнала
   брифа остаётся прежней).
3. Чтение — `gitcmd.show(config.MAIN_BRANCH, "templates/<имя>",
   repo=config.ROOT)` напрямую, не через `_main_branch_text` и не с диска
   или ветки задачи. Оформление — как у соседних компонентов роли:
   developer и spec_auditor — `_manifest_component`, analyst —
   `_journal_component`; метка `templates/<имя>`, тело в границе, sha256
   исходного текста — в журнал «бриф: компонент».
4. Шаблон не прочитан (git не ответил, файла нет) — бриф собирается,
   вместо компонента — пометка вне границы «шаблон templates/<имя> не
   прочитан: <причина> — прочитай его сам» и запись журнала шага от
   имени роли с действием «бриф: шаблон не прочитан». Ни падения, ни
   молчаливого пропуска.
5. Миссии analyst, developer, spec_auditor (`role_prompt.py`) говорят,
   что шаблон — в БРИФЕ РОЛИ ниже, и велят читать файл `templates/<имя>`
   с диска только если вместо шаблона в брифе стоит пометка «шаблон …
   не прочитан». Имя шаблона в миссии остаётся.
6. Тесты в `tests/` с заявками «Ловит мутацию»: developer не получил
   шаблон PLAN; analyst получил PLAN вместо SPEC и QUESTIONS; spec_auditor
   не получил SPEC-AUDIT; reviewer или test_author получили шаблон
   (вторая копия формы REVIEW); шаблон прочитан с диска или ветки задачи,
   а не с `main` (в песочнице `main` и диск расходятся — в брифе текст
   `main`); компонент шаблона без границы или без записи журнала, sha256
   записи не равен sha256 исходного текста шаблона до обёртки; при
   неудаче чтения компонент тихо пропал (нет пометки или записи журнала)
   либо сборка брифа упала; миссия developer велит читать
   `templates/PLAN.md` безусловно, без оговорки о пометке «не прочитан»;
   компонент шаблона поставлен перед существующими компонентами брифа
   (первая запись журнала «бриф: компонент» перестала быть прежней — у
   analyst картой, у developer и spec_auditor первым компонентом роли);
   analyst получил только один из двух шаблонов (SPEC без QUESTIONS или
   наоборот); неудача чтения записана не от имени роли шага (актор не
   равен роли) либо общим действием «бриф: компонент» вместо «бриф:
   шаблон не прочитан».
7. Раздел SPEC «Меняемое поведение» называет поимённо:
   `tests/test_brief.py::DeveloperBriefTest::test_assembles_three_
   components_and_journals_their_hashes`: `3` → `4`;
   `tests/test_brief.py::AnalystMapComponentTest::test_adds_only_the_
   map_and_journals_one_hash`: `1` → `3` (записи шаблонов — прочитанных
   или «не прочитан» — в песочнице без `templates/`). Остальные брифы в
   песочницах без `templates/` на `main` получат пометку «не прочитан»;
   их перечень аналитик определяет полным прогоном набора до гейта SPEC
   и вносит туда же. Ослабления утверждений нет.
8. `docs/codebase-map.md` обновляется в той же задаче.

Матрица неослабления: граница брифа не снимается — шаблон внутри
маркеров с непредсказуемым id; шаблоны читаются с `main` пульта, как
скилы, — роль не подменяет их правкой в своей ветке; неудача чтения не
скрывается (пометка и запись журнала) и не роняет шаг; опись и потолок
файла брифа developer/spec_auditor действуют на шаблон так же, как на
остальные компоненты; ревью-пакет и источник формы REVIEW не меняются;
`templates/` и `skills/` не меняются; `guard` не меняется.

Зоны: orchestrator/brief.py, orchestrator/role_prompt.py, tests/,
docs/codebase-map.md.

Только чтение (не менять): orchestrator/runner.py, orchestrator/review.py,
orchestrator/context_package.py, orchestrator/gitcmd.py,
orchestrator/config.py, scripts/guard.py, scripts/codebase_map.py,
templates/, skills/, CLAUDE.md, AGENTS.md, roles.yaml, gates.yaml,
targets.yaml, models.yaml, model_sets.yaml, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, .github/, **/conftest.py, pyproject.toml.

Не входит: записка следующему шагу и раздел «Чего не хватило» (К-2б);
формулировки «по templates/…» в `skills/spec-authoring.md` и других
скилах (защищённый путь, по смыслу не расходятся); шаблон для
test_author; изменение ревью-пакета; полный зелёный набор `tests/`, CI
ветки, неизменность защищённых путей и бюджет — их держит пульт.

Порядок: после 01M4R4JDG8RH53ZNWM0XF90CFJ.

Рамка: $40.

Набор моделей: по умолчанию.
