---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py / Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py / Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_awaiting_human_units.py, tests/test_epic_draft_promote_unsupported_project.py, tests/test_gitcmd_push_point.py, tests/test_mr_delivery_units.py, tests/test_push_hook_stand.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; в) защищённые пути: .github/, .github/workflows/, .github/workflows/ci.yml; г) budget_usd 85 ≥ 45; д) ТЗ ссылается на ADR: ADR-0029."
spec_sha: d4d80912f4e9177b7b262ff7e9ecccd362c428ad
schema_version: 5
---

# SPEC-AUDIT: Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor

Четвёртый визит аудита. Сравнил эту версию SPEC с прошлой (8429208c):
дифф автокоммитов `ed4c89ed0..64caf2988` ссылки документов. Изменились
три места, все переносят решение Оператора №2 с гейта SPEC:
- требование 7 — `ci.head_sha` убран из вызовов `gh`;
- AC-1 — добавлено условие о сетевом git;
- «Материалы» — исправлена записка о сети, добавлены записки по AC-4 и AC-8.

Код ветки с прошлого визита не менялся (HEAD 2b62f8a03).

Судьба трёх пунктов прошлого вердикта:
- п. 1 (проба AC-4 одним именем вне перечня) — решение №2.2 прямо относит
  её к замечаниям ревью и даёт надёжную формулу; снят;
- п. 2 (сетевой git по localhost) — закрыт новым условием AC-1 и
  исправленной запиской (решение №2.1);
- п. 3 (`ci.head_sha` в требовании 7) — исправлен.

## ТЗ и SPEC

- Требования ТЗ 1–9 и его критерии перенесены в требования SPEC 1–9 и в
  AC-1…AC-12 без потерь. ANSWER-1 (мандат на три файла с условиями
  матрицы, монолит, $85) отражён в требовании 10, AC-1, AC-2, AC-13 и в
  поле `budget_usd: 85`.
- Решения гейта SPEC №1.1–№1.4 и №2.1–№2.2 перенесены дословно по смыслу:
  - №2.1 — хвост AC-1 и записка о сети в «Материалах»;
  - №2.2 — требование 7, записки к AC-4 и AC-8.

  Противоречий между решениями нет: №2.1 явно исправляет утверждение №1.4.
- Требование 7 теперь согласовано с «Материалами»: `ci.head_sha` читает
  голову через git. Внутренних расхождений не нашёл.
- AC-4 считает `ok` ещё для `.github` и `**/.github/`, хотя ТЗ их не
  называет. Это прямо следует из формулы требования 3 ТЗ («любой записью,
  для которой формула истинна»), так что это уточнение, не новое
  требование.

## Факты против кода

Новые утверждения этой версии подтвердились:
- `tests/sandbox.py:951` — `_LOCAL_LOOPBACK_HOSTS = ("localhost",
  "127.0.0.1")`;
- `tests/sandbox.py:964-969` — `_is_local_git_address` пропускает
  `file://`, абсолютный путь, http(s) на loopback и голое имя remote;
- `tests/sandbox.py:996-1010` — `network_guarded_real_run` отказывает
  только прочим http(s)-адресам;
- записи файлов мандата несут `url: https://localhost/team/<имя>`
  (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:66`,
  `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:44`,
  `tests/test_epic_draft_promote_unsupported_project.py:31`). Записка о сети
  верна.
- Образец AC-1 `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:176`
  — заранее заведённый каталог клона (`(clone_path / ".git").mkdir`); `new`
  после этого не клонирует.
- Требование 7, адреса в `orchestrator/ci_rerun.py`:
  - `:156` — `ci.verifying_status`;
  - `:223` — `ci.check_run_workflow_run`;
  - `:250` — `ci.head_sha`, через git (`orchestrator/ci.py:237-254`);
  - `:274`, `:289` — `ci.failed_check_names`;
  - `:231`, `:308` — `ci.trigger_rerun`.
- Записка к AC-4 (решение №2.2): проверил формулу опытом (python3,
  `config.is_protected_path`, `orchestrator/config.py:818-849`). Имя берётся
  длиннее всех записей, первым символом не из следующих за
  `.github/workflows/`. Результат:
  - все пять случаев `ok` AC-4 — истина;
  - все одиннадцать случаев `fail` — ложь;
  - смешанный перечень `.github/workflows/a`, `.github/workflows/b`,
    `**/aaaa…` — ложь.

  Почему формула надёжна, видно из кода:
  - `**/<имя>` не совпадёт, потому что имя длиннее записи;
  - `**/<каталог>/` не зависит от имени;
  - префикс длиннее `.github/workflows/` отсекается первым символом.
- Записка к AC-8: `_hosting_registry` читает `forge.IMPLEMENTATIONS` в
  момент вызова (`orchestrator/targets.py:1163-1170`, реестр —
  `orchestrator/forge.py:365`). Подтверждено.
- Прочие факты прошлых визитов на том же HEAD не изменились:
  - `SUPPORTED_PAIRS` — `orchestrator/targets.py:25-33`;
  - `unsupported_reason` — `:292-313`;
  - `_check_delivery` — `:622-726`;
  - `_check_full_suite_source` — `:1137-1160`;
  - `trigger_rerun` — `orchestrator/ci.py:1793-1837`;
  - путь гейта — `orchestrator/fsm_merge_gate.py:319-338`;
  - `cleanup_project_remote` — `orchestrator/cleanup.py:279-333`, литерал на
    `:311`;
  - `_github_form_allowed` — `orchestrator/forge.py:165-191`.

Неподтверждённых утверждений не нашёл.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `SUPPORTED_PAIRS` без новой пары — `unsupported_reason` не `None`, действия отказывают. Новое условие о git ловит поддержанный случай, который дошёл до `git clone/push https://localhost/…`. До кода тест красный отказом поддержки и безопасен: до клона дело не доходит, `gh` подделан |
| AC-2 | да | лишняя пара `("gitlab","operator")`; правка текста `unsupported_reason` — равенство не сойдётся |
| AC-3 | да (закрепление) | исключение для GitHub в любом поле `_check_delivery`; отказ требования 8 поставлен до проверки вида — тексты разойдутся |
| AC-4 | да | для GitHub оставлено условие `full_suite` — строки нет; проба путём каталога — `**/` даст ложный `ok`; проба именем `ci.yml`/`x`/`a`/`main.yml`/на `c` — ловится записями на файл; маска через `mask_matches` — `.github/*` даст `ok`. Пробу именем вне перечня по решению №2.2 ловит ревью, формула дана в «Материалах» |
| AC-5 | да | `token_expiry` у `_GitHub`; `project-ci-reruns` без `full_suite` ci/both |
| AC-6 | да | `approve` проекта людей зовёт `pr merge`; `mr-sync --confirm` удаляет ветку на сервере; `kill` после отправки закрывает PR |
| AC-7 | да | отказ только в `ci_rerun.py` — прямой `trigger_rerun` зовёт `gh`; отказ после `ci_rerun.py:156` — шпион видит `gh api`; перевёрнутое условие — у `github` + `operator` нет `run rerun --failed`. До кода тест красный безопасно, через подделку `ci.gh` |
| AC-8 | да | признак по литералу — ловит подкласс `_GitHub` с `True`; признак через `CI_BY_PIPELINE` — ловит namespace GitLab с `READS = False`; отказ для `operator` — `github` + `operator` не загрузится |
| AC-9 | да | `_close_project_pr` до отправки для `target-human`; «PR не тронут» только в одной ветке; прежний текст после отправки потерян |
| AC-10 | да | «PR не тронут» дописан и для GitLab |
| AC-11 | да | `return rest == []` → `return True` (`orchestrator/forge.py:181`) |
| AC-12 | да | новый литерал хостинга вне разрешённых мест — сторож; условие строки doctor не через `ci_by_pipeline` — `tests/test_doctor_gitlab_ci_file.py:152-173` |
| AC-13 | да | удалён случай `gitlab` + `operator`; `==` → `in` в `test_ac3_*_reason_exact`; новый `skip`; константа или иная правка в файле эпика |

## Зоны

- Зоны SPEC покрывают все места правок:
  - `orchestrator/targets.py` — пара и отказ `ci_required_jobs`;
  - `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` — атрибут
    `READS_CI_REQUIRED_JOBS`;
  - `orchestrator/doctor/project_checks.py` — условие строки и файл CI;
  - `orchestrator/ci.py` — `trigger_rerun`;
  - `orchestrator/ci_rerun.py` — отказ до `:156`;
  - `orchestrator/cleanup.py`;
  - `docs/codebase-map.md`;
  - `tests/`.
- Модули «только чтение» правки не требуют.
- `.github/…` в сигналах — значения `no_paths` вымышленной записи. Файлы
  `.github/` репозитория не меняются, приложение PLAN не нужно, песочница
  ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Три файла мандата (`SUPPORTED_PAIRS`, тексты причин) | отказ неподдержанной пары во всех действиях; точный состав констант (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:149-391`, `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:188-313`, `tests/test_epic_draft_promote_unsupported_project.py:58-93`) | да, на `gitlab` + `operator` | те же файлы + AC-1, AC-2, AC-13 | ок по ANSWER-1 и решению №1.3 |
| `ci.trigger_rerun` для проекта людей | повтор флейка CI пультом (`orchestrator/ci.py:1793-1837`; тесты на записях `operator` — `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py:111`, `:549-573`, `:624-660`) | нет для `target-human` — решение 04.11 п. 1 | AC-7; прежние тесты `operator` не трогаются | ок |
| `ci-rerun` проекта людей | отказ вне `verifying` с текстом состояния (`orchestrator/ci_rerun.py:158-162`) | заменён более строгим отказом без `gh`; тестов команды на проект людей нет | AC-7 | ок |
| `kill` до отправки, `github` + `target-human` | закрытие PR (`orchestrator/cleanup.py:311-312`; тест `kill` — только `operator`) | нет для проекта людей — решение 04.11 п. 3 | AC-9, AC-10 | ок |
| Загрузка записи с `ci_required_jobs` | вид поля (`orchestrator/targets.py:696-698`); загрузка `github` + `operator` (`tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:55-68`, `:233`) | да + новый отказ (усиление); в `tests/` поле есть только у записей `operator` | AC-3, AC-8 | ок |
| Строка `project-ci-file-no-paths` | GitLab: только при `full_suite` ci/both (`tests/test_doctor_gitlab_ci_file.py:152-173`, `tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:521-569`) | да для GitLab; для GitHub — новая строка | AC-4, AC-12 | ок |
| Сторож литералов | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-488` | да | AC-12 | ок |

Существующих тестов, которые сломаются вне мандата, не нашёл. Искал по
`tests/` имена `trigger_rerun`, `cleanup_project_remote`,
`ci_required_jobs`, `check_ci_file_no_paths`, `SUPPORTED_PAIRS`. Раздела
«Меняемое поведение» в SPEC нет — смена ожиданий идёт только по мандату.

## Пути обхода гейтов

1. AC-4 как чёрный ящик не ловит пробу одним фиксированным именем вне
   перечня, например `q`. Решение №2.2 прямо делает это замечанием ревью и
   даёт формулу (проверена опытом, см. выше). По правилу о решениях
   Оператора отклонение не поднимается.
2. Сетевой git по localhost: новое условие AC-1 требует шпиона git и
   задаёт безопасную форму — заранее заведённый клон, голый локальный
   `origin` или ранний `Halt`. Обхода не вижу.

## Вердикт

pass. Отклонений нет. Пункты прошлого вердикта закрыты версией
d4d80912 (AC-1, требование 7, «Материалы») или сняты решением Оператора
№2.2 (проба AC-4 одним именем — ревью). Новые утверждения SPEC о коде
(`tests/sandbox.py:951`, `:964-969`, `:996-1010`;
`tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:176`;
`orchestrator/ci_rerun.py:250`, `orchestrator/ci.py:237-254`;
`orchestrator/targets.py:1163-1170`) и формула записки к AC-4 сверены с
кодом и опытом.
