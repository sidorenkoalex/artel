---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py / Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py / Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_awaiting_human_units.py, tests/test_epic_draft_promote_unsupported_project.py, tests/test_gitcmd_push_point.py, tests/test_mr_delivery_units.py, tests/test_push_hook_stand.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; в) защищённые пути: .github/, .github/workflows/, .github/workflows/ci.yml; г) budget_usd 85 ≥ 45; д) ТЗ ссылается на ADR: ADR-0029."
spec_sha: 2b14ff617fa5e671899ea0a765deb2b3245795bc
schema_version: 5
---

# SPEC-AUDIT: Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor

Второй визит аудита. Шесть отклонений прошлого визита (fail) в этой
версии SPEC сняты: AC-13 и требование 10 больше не требуют равенства там,
где на main вхождение; AC-7 и требование 7 больше не требуют «gh не вызван»
на всём пути approve (чтения статуса остаются, запрет только на вызовы из
`trigger_rerun`); отказ `ci-rerun` поставлен до `ci.verifying_status`
(`orchestrator/ci_rerun.py:156`); требование 3 говорит «для КАЖДОГО имени
файла»; признак, а не литерал в `targets.py`, проверяет подмена реестра
(AC-8); текст журнала `kill` после отправки задан (требование 9, AC-9).
Ниже — то, что осталось.

## ТЗ и SPEC

- Требования ТЗ 1–9 и критерии ТЗ перенесены в требования SPEC 1–9 и
  AC-1…AC-12 без потерь. Решения ANSWER-1 (мандат на три файла с
  условиями матрицы, монолит, $85) — требование 10, AC-1, AC-2, AC-13,
  `budget_usd: 85`.
- Уточнения сверх ТЗ, которые следуют из кода, а не добавляют объём:
  требование 7 называет место отказа `ci-rerun` (после проверок
  `--reason`, до `:156`) и смену прежнего отказа «задача в состоянии …»
  для проекта людей; требование 9 — текст журнала после отправки. ТЗ
  требует «ci-rerun … отказывает тем же текстом», и без этого места
  требование невыполнимо: `gh` зовётся до `trigger_rerun` на каждом
  пути команды.
- Расхождение (concerns, см. вердикт п. 2): требование 10 (SPEC.md,
  требование 10: «вид их утверждений — как на main … вхождение полного
  текста причины … `tests/test_epic_draft_promote_unsupported_project.py:87`»)
  и AC-13 («с константой нового текста целиком») расходятся для файла
  `epic draft promote`: на main там нет константы, причина вычисляется
  `targets.unsupported_reason(name)`
  (`tests/test_epic_draft_promote_unsupported_project.py:72`, `:87`).
  ANSWER-1 требует «точного нового текста причины» во всех действиях,
  в том числе `epic draft promote`, а «иные правки» запрещает. Выполнить
  AC-13 буквально — добавить константу (усиление, но вне буквы «вид как
  на main»); оставить вычисленную причину — AC-13 не выполнен.

## Факты против кода

Подтвердилось (рабочий каталог, HEAD 2b62f8a03):
- `SUPPORTED_PAIRS` и комментарий — `orchestrator/targets.py:25-33`;
  `unsupported_reason` — `orchestrator/targets.py:292-313`, перечень —
  `sorted(SUPPORTED_PAIRS)`; новый текст для `gitlab` + `operator` будет
  ровно «… (поддержаны: github + operator, github + target-human, gitlab +
  target-human)» (порядок `sorted` кортежей).
- `_check_delivery` — `orchestrator/targets.py:622-726`, хостинга не
  получает (аргументы `where, policy, machine`), зовётся из
  `merge_local` (`:475`) до `check` (`:478`); `ci_required_jobs` —
  `:696-698`. `_check_full_suite_source` — `:1137-1160`, реестр через
  `_hosting_registry` — `:1163-1170`; `forge.IMPLEMENTATIONS` —
  `orchestrator/forge.py:365`; у `_GitHub` нет `job_test_report`.
- `gitlab_adapter._required` — `orchestrator/gitlab_adapter.py:417-418`;
  `_GitHub` поля не читает.
- `project_entry_checks` — `orchestrator/doctor/project_checks.py:37-76`,
  условие строки — `:70-73`, `by_pipeline` — `:51`;
  `check_ci_file_no_paths(check_name, entry)` — `:740-750`, хостинга не
  знает (сигнатуру придётся расширить — в зоне); `project-ci-reruns` —
  `:450-452`; `token-expiry` строится только при `token_expiry` у
  реализации — `orchestrator/doctor/misc_checks.py:172-174`.
- Формула `config.is_protected_path` — `orchestrator/config.py:818-849`.
  Проверено опытом (python3, файлы `.github/workflows/ci.yml`,
  `.github/workflows/c`, `.github/workflows/zz/deep.yaml`,
  `.github/workflows/a`): покрывают все четыре `.github/workflows/`,
  `.github/`, `.github`, `**/workflows/`, `**/.github/` (а также любые
  строковые префиксы — `.github/workflow`, `.`, `""`); не покрывают все —
  `.github/*` (ни одного), `**/ci.yml`, `.github/workflows/c`,
  `.github/workflows/ci.yml`, `**/workflows`. Утверждение требования 3
  «ровно записи трёх видов» верно.
- `trigger_rerun` — `orchestrator/ci.py:1793-1837`, отказ GitLab через
  `_pipeline_project` (`:204-212`, `:1815-1817`); `rerun_started` —
  «не запущен» не в тексте (`:1854`), поэтому отказ «ре-ран CI не
  запущен: …» ведёт гейт на путь `flake-rate` «повтор не запущен»
  (`orchestrator/fsm_merge_gate.py:319-323`) и `sys.exit` «merge
  отклонён» (`:336-338`). Путь target-human к нему достижим:
  `_approve_for_project_people` → `_ci_ready_or_wait`
  (`orchestrator/fsm_merge_gate.py:1638`) → `_wait_for_branch_ci_green`
  → `_ci_confirm_red_or_flake` (`:383-385`).
- `ci-rerun`: проверки `--reason` — `orchestrator/ci_rerun.py:136-151`,
  `ci.verifying_status` — `:156`, состояние — `:158-162`, зависший путь —
  `:223`, красный — `:274`, `:289`, `trigger_rerun` — `:231`, `:308`.
- `cleanup_project_remote` — `orchestrator/cleanup.py:279-316`, текст
  после отправки — `:297-299`, `_forge_of(target) == "github"` — `:311`
  (исключение сторожа литералов,
  `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:430-435`);
  `_server_left_to_project_people` — `:319-333`.
- `forge._github_form_allowed` — `orchestrator/forge.py:165-191`,
  `return rest == []` — `:181`.
- `mr-sync --confirm` убирает только локальную ветку
  (`orchestrator/mr_sync.py:509-511`) — отправки в ветку задачи после
  `awaiting_human` нет, AC-6 выполним.

Не подтвердилось (мелкое, на решения не влияет):
- Требование 7: «`ci.head_sha` … на красном пути (`:250`)» среди
  вызовов `gh` — `ci.head_sha` читает голову локальным git
  (`orchestrator/ci.py:237-254`), `gh` не зовёт. Вывод требования (отказ до
  `:156`) от этого не меняется.
- Контекст и требование 7 называют `orchestrator/ci.py:257-282` местом
  `ci.branch_status` → `gh api …/check-runs`: там `check_runs_page`, сам
  `branch_status` — `orchestrator/ci.py:1206`. Ссылка на место вызова
  `gh`, не ошибка по существу.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `SUPPORTED_PAIRS` без новой пары — `unsupported_reason` не `None`, действия отказывают; до кода — красный отказом поддержки. Отклонение п. 4: форма безопасности задана только для `gh` |
| AC-2 | да | лишняя пара `("gitlab","operator")` в `SUPPORTED_PAIRS`; правка текста `unsupported_reason` (порядок, префикс) — равенство не сойдётся |
| AC-3 | да (закрепление) | новый отказ `ci_required_jobs` (треб. 8) поставлен до проверки вида в `_check_delivery` — для `ci_required_jobs: "x"` текст GitHub разойдётся с GitLab; исключение для GitHub в любом поле |
| AC-4 | частично | условие `_ci_components` оставлено для GitHub — строки нет; проверка `rel == ".github/workflows/"` вместо формулы — `.github`/`**/workflows/` дадут `fail`; маска `*` через `mask_matches` — `.github/*` даст `ok`. НЕ ловит: пробу одним фиксированным именем файла, отличным от `ci.yml` и `c…` (отклонение п. 1) |
| AC-5 | да | `token_expiry` добавлен `_GitHub`; `project-ci-reruns` построен без `full_suite` ci/both |
| AC-6 | да | `approve` проекта людей зовёт `pr merge`; `mr-sync --confirm` удаляет ветку на сервере; `kill` после отправки закрывает PR |
| AC-7 | да | отказ только в `ci_rerun.py`, не в `trigger_rerun` — прямой вызов зовёт `gh`; отказ `ci-rerun` после `:156` — шпион видит `gh api`; проверка по литералу/`operator` перевёрнута — у `github` + `operator` нет `run rerun --failed`. До кода — красный безопасно: `ci.gh` подделка, `gh run watch` подделки возвращается сразу |
| AC-8 | да | признак по литералу `forge == "github"` — подмены реестра (обе стороны) это ловят; отказ для записи `operator` — `github` + `operator` не загрузится |
| AC-9 | да | `_close_project_pr` зовётся до отправки для `target-human`; «PR не тронут» только в одной из веток; прежний текст после отправки потерян |
| AC-10 | да | «PR не тронут» дописан и GitLab |
| AC-11 | да | `return rest == []` → `return True` |
| AC-12 | да | любая из правок ломает сторож литералов (`cleanup.py` вне `cleanup_project_remote`/`_forge_of`) или прежние тесты; в т.ч. `tests/test_doctor_gitlab_ci_file.py:152-173` (условие строки должно идти через `doctor.forge.ci_by_pipeline`, его тест подменяет) |
| AC-13 | да | удалён случай `gitlab` + `operator`; `==` → `in` в `test_ac3_*_reason_exact`; новый `skip`. Отклонение п. 2 — константа в файле эпика |

## Зоны

- Зоны SPEC покрывают все места правок: `targets.py` (пара, отказ
  `ci_required_jobs` — в `check`/`merge_local` или расширенной сигнатуре
  `_check_delivery`), `forge.py`/`gitlab_adapter.py` (признак),
  `doctor/project_checks.py` (условие и сигнатура `check_ci_file_no_paths`),
  `ci.py` (`trigger_rerun`), `ci_rerun.py` (отказ до `:156`; понадобится
  импорт `targets` — в зоне), `cleanup.py`, `docs/codebase-map.md`,
  `tests/`.
- Модули «только чтение» правок не требуют: гейт мержа получает отказ из
  `trigger_rerun` (`orchestrator/fsm_merge_gate.py:313`), `doctor/cli.py` и
  `misc_checks.py` уже дают нужные исходы.
- Защищённые пути (`.github/…` в сигналах) — значения `no_paths`
  вымышленной записи в песочнице, файлы `.github/` репозитория не
  меняются (раздел «Не входит»). Приложение PLAN не нужно. Песочница
  ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Три файла мандата (`SUPPORTED_PAIRS`, тексты причин) | отказ неподдержанной пары во всех действиях; точный состав констант (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:149-391`, `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:188-313`, `tests/test_epic_draft_promote_unsupported_project.py:58-93`) | да, на `gitlab` + `operator` | те же файлы + AC-1, AC-2, AC-13 | ок по ANSWER-1; п. 2 вердикта — константа в файле эпика |
| `ci.trigger_rerun` для проекта людей | повтор флейка CI пультом (`orchestrator/ci.py:1793-1837`; `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py:549-573`, `:624-660` — записи `operator`) | нет для `target-human` — решение Оператора 04.11 п. 1 (ADR-0029 «Не входит») | AC-7; прежние тесты на `operator` (`tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py:111`, `tests/test_ci_project_gh_address.py:38`) не трогаются | ок |
| `ci-rerun` проекта людей | отказ вне `verifying` с текстом состояния (`orchestrator/ci_rerun.py:158-162`) | заменён отказом «ре-ран CI не запущен» — сильнее (без `gh`); тестов на проект людей у команды нет (`tests/test_ci_rerun_command.py` — артель) | AC-7 | ок |
| `kill` до отправки, `github` + `target-human` | закрытие PR (`orchestrator/cleanup.py:311-312`; `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py` — только `operator`, `:74`) | нет для проекта людей — решение Оператора 04.11 п. 3 | AC-9, AC-10; `operator` — прежний тест | ок |
| Загрузка записи с `ci_required_jobs` | вид поля (`orchestrator/targets.py:696-698`); `github` + `operator` загружается (`tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:55-68`, `:233`) | да + новый отказ (усиление) | AC-3, AC-8 | ок; п. 3 вердикта — пустой список |
| Строка `project-ci-file-no-paths` | GitLab: строка только при `full_suite` ci/both (`tests/test_doctor_gitlab_ci_file.py:152-173`, `tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:521-569`) | да для GitLab; для GitHub — новая строка | AC-4, AC-12 | ок; п. 1 вердикта |
| Сторож литералов | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-488` | да | AC-12 | ок |

Тесты, вызывающие меняемые функции, проверены поиском по `tests/`:
`trigger_rerun` — подменён в `tests/test_ci_callers_project_repo.py`,
настоящий — на записях `operator` (`tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py:111`)
и `gitlab` + `operator` (`tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:88`, `:1286-1315`);
`cleanup_project_remote` — тест `kill` на `operator`; предикат
`_server_left_to_project_people` (`tests/test_awaiting_human_units.py:127-152`)
не меняется; текст «сервер проекта не тронут» в тестах не утверждается;
тесты части 1 включают пару подменой `SUPPORTED_PAIRS` и `pr close`/`run
rerun` для `target-human` не ждут
(`tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py:666-702`).
Сломанного существующего теста вне мандата не нашёл.

## Пути обхода гейтов

1. Требование 3 запрещает пробу конкретным именем файла, но AC-4 её не
   ловит: реализация `is_protected_path(".github/workflows/x", no_paths)`
   (одно фиксированное имя, не `ci.yml` и не начинающееся с `c`) проходит
   все случаи AC-4 — `.github/workflows/c`, `**/ci.yml`,
   `.github/workflows/ci.yml` для имени `x` дают `False`, т.е. `fail`, как
   и ждёт критерий. Ложный `ok` такая реализация даст для `**/x` или
   `.github/workflows/x` — значений, которых в AC-4 нет. Чёрный ящик
   произвольное имя не поймает. Поможет больше распространённых имён
   (`**/main.yml`, `**/ci.yaml`, `**/test.yml`, `.github/workflows/m`) или
   то, что ревью проверит, что выбор идёт по самой записи (префикс
   `.github/workflows/` либо `**/workflows/`/`**/.github/`).
2. AC-1: поддержанные `run`/`auto`/`approve` ограничены только по `gh`.
   Фикстура `halted` (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:87-92`)
   останавливает `runner.spawn_agent` и `fsm.cmd_advance`, но не путь
   `approve` на `merge_gate`, а запись в файлах мандата несёт
   `url: https://localhost/team/<имя>` (`:66`). Буква AC-1 допускает
   тест, в котором `approve` проекта людей доходит до сетевого git по
   этому адресу (`_ensure_branch_head_published`, отправка). ТЗ
   («`origin` — локальный голый репозиторий») этого не допускает, а SPEC
   не задаёт безопасную форму для git.

## Вердикт

concerns. Отклонений, из-за которых SPEC нужно вернуть аналитику, нет:
все решаются на гейте.

1. AC-4 не ловит мутацию, которую запрещает требование 3: пробу одним
   фиксированным именем файла (SPEC.md, требование 3 «Проба одним или
   несколькими конкретными именами … не доказывает» против перечня
   AC-4). Решение Оператора: добавить имена в AC-4 или оставить это
   свойство ревью.
2. Требование 10 и AC-13 расходятся для
   `tests/test_epic_draft_promote_unsupported_project.py:72`, `:87`: на
   main причина вычисляется, а AC-13 требует «константу нового текста
   целиком». Решение Оператора: разрешить константу в этом файле
   (усиление) или снять для него слова «с константой».
3. Требование 8 и AC-8 не говорят, «задано» ли `ci_required_jobs: []`
   (`orchestrator/targets.py:696` — умолчание `[]`): отказывать по
   наличию ключа или по непустому списку — выбор исполнителя. Риск
   малый: пустой список гарантии не обещает.
4. AC-1 задаёт безопасную форму только для `gh`, не для сетевого git
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:66`,
   `:87-92`). Нужна строка: поддержанные случаи останавливаются `Halt`
   до клона и отправки, либо `origin` — локальный голый репозиторий.
5. Мелкое по фактам: `ci.head_sha` — git, не `gh`
   (`orchestrator/ci.py:237-254`, требование 7); место `branch_status` —
   `orchestrator/ci.py:1206`, а не `:257-282`. На требования не влияет.
