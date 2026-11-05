---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py / Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py / Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_awaiting_human_units.py, tests/test_epic_draft_promote_unsupported_project.py, tests/test_gitcmd_push_point.py, tests/test_mr_delivery_units.py, tests/test_push_hook_stand.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; в) защищённые пути: .github/, .github/workflows/, .github/workflows/ci.yml; г) budget_usd 85 ≥ 45; д) ТЗ ссылается на ADR: ADR-0029."
spec_sha: 8429208c9af5a7a747b68e05eccff80d199fd764
schema_version: 5
---

# SPEC-AUDIT: Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor

Третий визит аудита. Сравнил эту версию SPEC с прошлой (2b14ff61): дифф
автокоммитов `31165dad9..ed4c89ed0` ссылки документов. Изменились
требования 3 и 8, AC-4, AC-8, AC-13 и раздел «Материалы». Все правки
переносят решения Оператора 1–4 с гейта SPEC. Из пяти пунктов прошлого
вердикта: п. 1 (AC-4) сужен, но не закрыт полностью; п. 2 (файл эпика)
снят решением 3; п. 3 (`[]`) снят решением 1 («не закрепляется»); п. 4
(сетевой git) снят решением 4, но факт в нём неточен (см. ниже); п. 5
перенесён в записки разработчику.

## ТЗ и SPEC

- Требования ТЗ 1–9 и критерии ТЗ перенесены в требования SPEC 1–9 и
  AC-1…AC-12 без потерь. ANSWER-1 (мандат на три файла с условиями
  матрицы, монолит, $85) отражён в требовании 10, AC-1, AC-2, AC-13 и
  поле `budget_usd: 85`.
- Решения гейта SPEC перенесены дословно по смыслу:
  - решение 1 — требование 8 и AC-8 (`READS_CI_REQUIRED_JOBS`, `getattr`
    по реестру, две подстановки, `[]` не закрепляется);
  - решение 2 — требование 3 (запрет пробы путём каталога и одним именем)
    и перечень `fail` в AC-4;
  - решение 3 — AC-13 для файла эпика (причина вычисляется, новой
    константы нет);
  - решение 4 — записки в «Материалах».
- Расхождение решения 2 с ТЗ: ТЗ и решение 2 называют `ok` для
  `.github/workflows/`, `.github/` и `**/workflows/`. AC-4 добавляет к ним
  `.github` и `**/.github/`. Это следует из формулы требования 3 ТЗ
  («любой записью, для которой формула истинна»), так что это уточнение, а
  не новое требование.
- Внутреннее расхождение (мелкое): требование 7 по-прежнему относит
  `ci.head_sha` («на красном пути (`:250`)») к вызовам `gh`. «Материалы»
  же по решению 4 говорят, что `ci.head_sha` читает голову через git
  (`orchestrator/ci.py:237-254`). Вывод требования 7 (отказ до
  `orchestrator/ci_rerun.py:156`) от этого не меняется.

## Факты против кода

Подтвердилось (рабочий каталог, HEAD 2b62f8a03):
- `SUPPORTED_PAIRS` и комментарий над ним — `orchestrator/targets.py:25-33`.
  `unsupported_reason` — `orchestrator/targets.py:292-313`, перечень пар —
  `sorted(SUPPORTED_PAIRS)`. Текст AC-2 соответствует порядку `sorted`.
- `_check_delivery` — `orchestrator/targets.py:622-726`, хостинг ему не
  передаётся. `_check_full_suite_source` — `:1137-1160` (образец:
  `getattr(_hosting_registry().get(hosting), "job_test_report", None)`,
  `:1156`). `_hosting_registry` — `:1163-1170`.
- `forge.IMPLEMENTATIONS = {"github": _GitHub, "gitlab": gitlab_adapter}` —
  `orchestrator/forge.py:365`. Реестр держит класс и модуль, поэтому
  атрибут класса или модуля `READS_CI_REQUIRED_JOBS` через `getattr`
  читается. `_GitHub.CI_BY_PIPELINE = False` — `forge.py:222`,
  `gitlab_adapter.CI_BY_PIPELINE = True` — `gitlab_adapter.py:44`,
  `ci_by_pipeline` — `forge.py:395-399`. Обе подстановки AC-8 выполнимы:
  подкласс `_GitHub` и пространство имён с атрибутами `gitlab_adapter`.
- Решение 2, утверждение о формуле — проверено опытом (python3, функция
  `config.is_protected_path`, `orchestrator/config.py:818-849`):
  - проба путём `.github/workflows/` даёт истину для `**/`
    (`rest == ""` совпадает с пустым последним компонентом), а все файлы
    под каталогом `**/` не покрывает;
  - все семь проб (`ci.yml`, `x`, `a`, `main.yml`, `c`, `q`,
    `zz/deep.yaml`) покрывают `.github/workflows/`, `.github/`, `.github`,
    `**/workflows/` и `**/.github/`;
  - ни одной пробы не покрывают `.github/*`, `**/ci.yml`, `**/x`, `**/a`,
    `**/main.yml`, `.github/workflows/c`, `.github/workflows/ci.yml`,
    `.github/workflows/x`, `.github/workflows/a`.

  Перечни `ok`/`fail` в AC-4 с формулой согласны.
- Решение 3: `tests/test_epic_draft_promote_unsupported_project.py:72-73`,
  `:87` — причина вычисляется `targets.unsupported_reason(name)`, с
  `assert reason` и `assert reason in out`. Подтверждено.
- Решение 4: `ci.head_sha` — git (`orchestrator/ci.py:237-254`),
  `branch_status` — `orchestrator/ci.py:1206`, литерал
  `_forge_of(target) == "github"` — `orchestrator/cleanup.py:311`.
  Подтверждено.
- Прочие факты прошлых визитов не изменились: `trigger_rerun` —
  `ci.py:1793-1837`; путь `flake-rate`/«merge отклонён» —
  `fsm_merge_gate.py:319-338`; места `ci-rerun` — `ci_rerun.py:136-162`,
  `:223`, `:231`, `:274`, `:289`, `:308`; `cleanup_project_remote` —
  `cleanup.py:279-333`; `_github_form_allowed` — `forge.py:165-191`.

Не подтвердилось:
- Решение 4: «сетевой git в тестах недостижим песочницей
  (`tests/sandbox.py:996-1010`, `:1337-1341`)» — верно только для внешней
  сети:
  - `network_guarded_real_run` считает адреса `https://localhost` и
    `https://127.0.0.1` локальными (`tests/sandbox.py:951`, `:964-968`) и
    отдаёт их настоящему git; голое имя remote (`origin`) тоже идёт в
    настоящий git (`:969`);
  - перехват действует только там, где тест поставил `SpyRun`
    (`tests/sandbox.py:1705-1708`, фикстуры `initialized_tmp_root` и
    подобные).

  Записи файлов мандата несут `url: https://localhost/team/<имя>`
  (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:66`,
  `tests/test_epic_draft_promote_unsupported_project.py:31`). Поэтому
  поддержанный случай `epic draft promote`/`new`/`approve`, дошедший до
  клона или отправки, запустит настоящий `git clone/push
  https://localhost/…`. Наружу он не уйдёт, но и не «недостижим»: при
  локальном сервере на 443 исход зависит от машины.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `SUPPORTED_PAIRS` без новой пары — `unsupported_reason` не `None`, действия отказывают. До кода — красный отказом поддержки, безопасно (`gh` подделан). Остаток по git — п. 2 вердикта |
| AC-2 | да | лишняя пара `("gitlab","operator")`; правка текста `unsupported_reason` — равенство не сойдётся |
| AC-3 | да (закрепление) | отказ требования 8 поставлен до проверки вида в `_check_delivery` — тексты GitHub и GitLab разойдутся; исключение для GitHub в любом поле |
| AC-4 | да, с остатком | условие `full_suite` для GitHub оставлено — строки нет; проба путём каталога — `**/` даст ложный `ok` (теперь в перечне, ловится); проба именем `ci.yml`/`x`/`a`/`main.yml` — ловится записями `**/<имя>` и `.github/workflows/<имя>`; маска через `mask_matches` — `.github/*` даст `ok`. НЕ ловит: пробу одним (или двумя) фиксированными именами вне перечня (например `q`: все случаи `fail` AC-4 для него ложны, все `ok` истинны — опыт выше). П. 1 вердикта |
| AC-5 | да | `token_expiry` у `_GitHub`; `project-ci-reruns` без `full_suite` ci/both |
| AC-6 | да | `approve` проекта людей зовёт `pr merge`; `mr-sync --confirm` удаляет ветку на сервере; `kill` после отправки закрывает PR |
| AC-7 | да | отказ только в `ci_rerun.py` — прямой вызов `trigger_rerun` зовёт `gh`; отказ после `ci_rerun.py:156` — шпион видит `gh api`; перевёрнутое условие — у `github` + `operator` нет `run rerun --failed`. До кода — красный безопасно (подделка `ci.gh`) |
| AC-8 | да | признак по литералу `"github"` — подстановка подкласса `_GitHub` с `True` это ловит; признак через `CI_BY_PIPELINE` — подстановка namespace GitLab с `CI_BY_PIPELINE = True`, `READS = False` это ловит; отказ для `operator` — `github` + `operator` не загрузится |
| AC-9 | да | `_close_project_pr` до отправки для `target-human`; «PR не тронут» только в одной ветке; прежний текст после отправки потерян |
| AC-10 | да | «PR не тронут» дописан и для GitLab |
| AC-11 | да | `return rest == []` → `return True` (`forge.py:181`) |
| AC-12 | да | новый литерал хостинга вне разрешённых мест — сторож; условие строки doctor не через `doctor.forge.ci_by_pipeline` — `tests/test_doctor_gitlab_ci_file.py:152-173` |
| AC-13 | да | удалён случай `gitlab` + `operator`; `==` → `in` в `test_ac3_*_reason_exact`; новый `skip`; константа или иная правка в файле эпика |

## Зоны

- Зоны SPEC покрывают все места правок:
  - `targets.py` — пара и отказ `ci_required_jobs`;
  - `forge.py`/`gitlab_adapter.py` — атрибут `READS_CI_REQUIRED_JOBS`;
  - `doctor/project_checks.py` — условие строки и выбор файла CI;
  - `ci.py` — `trigger_rerun`;
  - `ci_rerun.py` — отказ до `:156`;
  - `cleanup.py`;
  - `docs/codebase-map.md`;
  - `tests/`.
- Модулям «только чтение» правка не нужна: гейт мержа получает отказ из
  `trigger_rerun`.
- `.github/…` в сигналах — значения `no_paths` вымышленной записи. Файлы
  `.github/` репозитория не меняются, приложение PLAN не нужно, песочница
  ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Три файла мандата (`SUPPORTED_PAIRS`, тексты причин) | отказ неподдержанной пары во всех действиях; точный состав констант (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:149-391`, `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:188-313`, `tests/test_epic_draft_promote_unsupported_project.py:58-93`) | да, на `gitlab` + `operator` | те же файлы + AC-1, AC-2, AC-13 (в файле эпика — вычисленная причина, решение 3) | ок по ANSWER-1 и решению 3 |
| `ci.trigger_rerun` для проекта людей | повтор флейка CI пультом (`orchestrator/ci.py:1793-1837`; тесты на записях `operator` — `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py:111`, `:549-573`, `:624-660`) | нет для `target-human` — решение Оператора 04.11 п. 1 | AC-7; прежние тесты `operator` не трогаются | ок |
| `ci-rerun` проекта людей | отказ вне `verifying` с текстом состояния (`orchestrator/ci_rerun.py:158-162`) | заменён более строгим отказом без `gh`; тестов команды на проект людей нет | AC-7 | ок |
| `kill` до отправки, `github` + `target-human` | закрытие PR (`orchestrator/cleanup.py:311-312`; тест `kill` — только `operator`) | нет для проекта людей — решение 04.11 п. 3 | AC-9, AC-10 | ок |
| Загрузка записи с `ci_required_jobs` | вид поля (`orchestrator/targets.py:696-698`); загрузка `github` + `operator` (`tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:55-68`, `:233`) | да + новый отказ (усиление); в `tests/` поле есть только у записей `operator` | AC-3, AC-8 | ок |
| Строка `project-ci-file-no-paths` | GitLab: только при `full_suite` ci/both (`tests/test_doctor_gitlab_ci_file.py:152-173`, `tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:521-569`) | да для GitLab; для GitHub — новая строка | AC-4, AC-12 | ок; остаток п. 1 |
| Сторож литералов | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-488` | да | AC-12 | ок |

Существующих тестов, которые сломаются вне мандата, не нашёл. Поиск шёл по
`tests/` по именам `trigger_rerun`, `cleanup_project_remote`,
`ci_required_jobs`, `check_ci_file_no_paths`, `SUPPORTED_PAIRS`.

## Пути обхода гейтов

1. Требование 3 запрещает пробу фиксированным именем, но AC-4 как чёрный
   ящик ловит её только для имён `ci.yml`, `x`, `a`, `main.yml` и имён на
   `c`. Реализация `is_protected_path(".github/workflows/q", no_paths)`
   проходит все случаи AC-4 (опыт выше). Ложный `ok` она даст для `**/q`.
   Произвольное имя чёрный ящик не поймает. Остаётся ревью: выбор должен
   идти по виду самой записи — строковый префикс `.github/workflows/` либо
   `**/workflows/`/`**/.github/`.
2. AC-1 задаёт безопасную форму только для `gh`. Поддержанный случай,
   дошедший до клона или отправки, отдаёт `https://localhost/…`
   настоящему git (`tests/sandbox.py:951`, `:964-969`). Решение 4 считает
   это недостижимым — см. «Факты против кода».

## Вердикт

concerns. Ни одно отклонение не требует вернуть SPEC аналитику, все
решаются на гейте.

1. AC-4 (SPEC.md, AC-4; требование 3) по-прежнему не ловит пробу одним
   фиксированным именем вне перечня (`q`, `probe.yml`, …). Для таких имён
   все исходы AC-4 совпадают с правильной реализацией
   (`orchestrator/config.py:840-848`). Варианты: оставить свойство ревью
   или добавить в AC-4 случай на запись-«файл» с именем, которое выберет
   сама реализация. Чёрным ящиком второе невыполнимо, так что по сути —
   ревью.
2. Решение 4 / «Материалы» SPEC: «сетевой git в тестах недостижим
   песочницей» неточно. `network_guarded_real_run` пропускает
   `https://localhost` и имена remote в настоящий git
   (`tests/sandbox.py:951`, `:964-969`, `:1405`), а записи файлов мандата
   несут такой адрес
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:66`,
   `tests/test_epic_draft_promote_unsupported_project.py:31`). Внешней
   сети нет, но поддержанные случаи AC-1 (`epic draft promote`, `new`,
   `approve`) могут исполнить настоящий `git clone/push` по localhost.
   Нужна строка в AC-1: поддержанные случаи останавливаются до клона и
   отправки (`Halt`) либо `origin` — локальный голый репозиторий.
3. Мелкое: требование 7 («`ci.head_sha` … на красном пути (`:250`)»
   среди вызовов `gh`) противоречит «Материалам» (`ci.head_sha` — git,
   `orchestrator/ci.py:237-254`). На критерии не влияет.
