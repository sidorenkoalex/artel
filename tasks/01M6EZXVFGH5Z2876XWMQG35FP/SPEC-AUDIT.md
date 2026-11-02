---
task: 01M6EZXVFGH5Z2876XWMQG35FP
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py; д) ТЗ ссылается на ADR: ADR-0029
spec_sha: 6de28bb8a29d88a791bffd5dfd2c4fe661a93f87
schema_version: 5
---

# SPEC-AUDIT: GitLab Б2.3-3: строки doctor проекта и forge-probe по ветке или коммиту

Аудит после возврата 1 (прошлый вердикт `fail` на sha 16b7125e). ANSWER-n у
задачи нет, решений Оператора на гейте SPEC в брифе нет.

Отклонения возврата 1 закрыты: поле кода названо (`http_status`, SPEC
треб. 4), проведение кода через `_read_all`/`_pipeline_findings` включено
в заполнение поля (треб. 4), имена и место строк 8–10 заданы (треб. 8–10),
у AC-3/5/6/7 есть парные «зелёные» случаи, AC-2 требует имена защит,
область строк 8–10 — `targets.merged_by_project_people` (треб. 1), выбор
`project-ci-token` — только `ci_by_pipeline` (треб. 1), проба подмодулей —
`gitcmd.in_repo ls-remote` (треб. 10), `branch_template` без `catalog`
(треб. 6), новый AST-сторож (AC-15), семантика `workflow:rules` (треб. 6),
охват перезапусков (треб. 9). Ниже — что осталось и что нашлось заново.

## ТЗ и SPEC
Сверено ТЗ (TZ.md:23-56) с SPEC (требования 1–13, AC-1…AC-15).

- Все пункты ТЗ отражены: п. 1 (пять строк) — треб. 3, 6, 8, 9, 10; п. 2
  (выбор по реестру, без `gh`, поле кода, четыре строки) — треб. 1, 2, 4,
  5, 6, 7; п. 3 — треб. 12; критерии ТЗ — AC-1…AC-15. Требований сверх ТЗ
  нет: треб. 11 и 13 повторяют «только чтение» и «github + operator
  прежние» ТЗ.
- Расхождение с ADR-0029 п. 6 (`docs/adr/0029*.md:55` — «если запись
  называет файл конвейера») снято: ТЗ:35 прямо называет `.gitlab-ci.yml`,
  SPEC фиксирует это в «Не входит».
- Квалификатор «с `target-human`» (ТЗ:24) SPEC применяет к строкам 8–10, а
  строки защит и `workflow` (треб. 3, 6) — ко всем записям GitLab, как
  требует ТЗ п. 2 (TZ.md:33, :36). Противоречия нет.

Отклонений нет.

## Факты против кода
Подтвердилось (рабочий каталог, df354e409):
- `project_entry_checks` `orchestrator/doctor/project_checks.py:34-58`,
  `ROLE_SKIP`-обёртки `:46-55`; `check_ci_pull_request` `:138`,
  `check_base_protection` `:176` (`gh api` `:193-196`), `_operator_gh_token`
  `:211`, `check_project_token` `:225`, `_GhProbe.denied` `:268-271`,
  `check_ci_token` `:300`, текст «статус CI проекта пульт не увидит»
  `:341-345`, `check_no_paths` `:359`, `component_checks` `:400`.
- `forge.PipelineStatus` `orchestrator/forge.py:42-50`, `Protections`
  `:99-103`, `ProjectInfo` `:106-110`, `BranchPipeline` `:113-119` — только
  `reason`; `_GitHub.pipeline_status` `:132-159`; `IMPLEMENTATIONS` `:163`;
  `ci_by_pipeline` `:193-197` (читает `targets.target(name)`, не `entry`).
- `Reply.status` `orchestrator/gitlab_adapter.py:76-87`; `transport` `:90`;
  `request` возвращает статус в `Reply` `:261-269`, `TimeoutError` →
  `Reply` без статуса `:250-252`; `_read_all` теряет статус `:289-291`;
  `_pipeline_findings` — отказ заданий `:382-385`; `protections` `:580-590`
  (две выдачи, вторая — `protected_tags`), `branch_pipeline` `:608-626`.
- `targets.DEFAULT_BRANCH_TEMPLATE` `orchestrator/targets.py:364`,
  `merged_by_project_people` `:566-570`, `RERUN_FLAGS`/`RERUN_PLUGINS`
  `:1109-1111`, `_rerun_argument` `:1114-1124`; `catalog.branch_name`
  (id в нижнем регистре) `orchestrator/catalog.py:633-639`.
- `gitcmd._hosting_project` `orchestrator/gitcmd.py:98-122` (по `-C
  <клон>` находит проект), токен слота — `git` `:1005-1011`, `in_repo`
  `:1221-1250`; `ls-remote` в `HOSTING_SUBCOMMANDS` `:41`.
- Фасад `doctor` несёт `forge`, `gitcmd`, `project_profile`, `targets`
  (`orchestrator/doctor/__init__.py:99-102`).
- `forge-probe` `orchestrator/artel.py:2371-2457`, конвейер базы `:2436`,
  `--job` по его sha `:2444-2449`.
- Сторож ac9 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:409-471`,
  `EXEMPT` `:416-421`; `field_like` `forge.hosting(...)` не видит (`:425-442`).
- Сейчас в `project_checks.py` нет сравнений с литералами `github`/
  `gitlab`/`operator`/`target-human` — новый сторож AC-15 на main зелёный.

Не подтвердилось:
- **Б-1 (мелкое).** SPEC «Обозначения»: `targets.py:566-570` — «единственное
  место сравнения `merge_gate` с литералом». Неверно: соседний предикат
  сравнивает `merge_gate != "operator"` в `orchestrator/targets.py:563`. На
  требования не влияет.
- **Б-2. Разбора YAML для файла CI в пульте нет, SPEC это не называет.**
  Треб. 6 и 9 требуют разобрать `.gitlab-ci.yml` (`workflow:rules` — блочный
  список отображений, `script` — блочный список, `extends:`, `default:`).
  PyYAML сознательно не используется, а общий разбор `yamlmini` блочных
  списков `- элемент`, якорей и многострочных скаляров не поддерживает и
  отказывает ошибкой (`orchestrator/yamlmini.py:1-24`). `yamlmini.py` вне
  зон, фасад его не несёт. Значит, разработчик пишет второй разборщик YAML
  внутри `project_checks.py` — вразрез с принципом «один разбор на всех
  читателей» (`yamlmini.py:3-6`) и с заметной долей рамки $40. SPEC не
  говорит ни где живёт разбор, ни какое подмножество YAML обязательно
  (якоря `<<: *x`, многострочный `script: |`, несколько документов).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | порог `< 30`; `fail` вместо `skip`; `project_info.reason` → `fail`. Не ловит: `access_level None` → не `skip` (случая нет), мелко |
| AC-2 | да | `<=` вместо `<`; постоянный `ok` без чтения `protections` (имена в тексте) |
| AC-3 | да, с оговоркой | постоянный `warn` (парный `feature/{id}` → `ok`); нет `if` в тексте. «В тексте `1`» — слабо: цифра `1` может прийти из образцового имени ветки, сдвиг нумерации на 0 её не уронит (В-4) |
| AC-4 | да, с оговоркой | `when: never` игнорируется (выдало бы `ok` по правилу 2); отсутствие `workflow` → не `ok`. Не ловит: отчёт обо всех правилах вместо сработавшего; ветку `include:` → `skip` (случая нет) |
| AC-5 | да | постоянный `fail`/`ok`; проверка не того файла |
| AC-6 | частично | `--reruns` в `script`; `retry` у `ci_job`; `retry` по всему файлу (парный случай). Не ловит пропуск `default:`/`extends:`, `variables`/`PYTEST_ADDOPTS`, `-p rerunfailures`, установки плагина, `retry: 0` — всё из треб. 9 без критерия (В-3) |
| AC-7 | да | постоянный `ok`/`fail`; проба в процессе роли; причина без stderr. Не ловит фильтр «тот же хост» и разрешение `../…` (случаев нет), мелко |
| AC-8 | да | выбор строк 8–10 по `ci_by_pipeline` вместо `target-human`; строки без условия |
| AC-9 | да, с оговоркой | оставленный `gh api`/`gh auth token` для GitLab — **только если тест подменяет `shutil.which("gh")` найденным путём**: на машине без `gh` код main возвращает раньше вызова (`project_checks.py:183-184`, `:212-213`) и AC-9 проходит пусто (В-2) |
| AC-10 | да | прежние GitHub-пути и тексты; строки не `ok` |
| AC-11 | да | различение по тексту `reason` (одинаковый `reason`); `fail` на любой `http_status` (503 → `skip`). Не ловит ветку `ok` при `verdict` `none`/`red` с непустым `reason` (В-1) |
| AC-12 | частично | поле не проведено через `_read_all`/`_pipeline_findings`/вторую выдачу `protections`; таймаут ≠ `None`. **Не ловит заполнение поля разбором текста `reason`** — все тексты `_status_reason` несут код (`gitlab_adapter.py:197-211`), а AC требует их неизменности (Е-1) |
| AC-13 | да | слот не проверяется; `gh auth token` при слоте; текст без «не делалась» |
| AC-14 | да | `--ref`/`--sha` игнорируются; оба флага вместе без отказа; смена вывода без флагов |
| AC-15 | частично | `forge.hosting(name) == "gitlab"`, `x in ("gitlab",)`, `is gitlab_adapter`. Не ловит выбор через словарь, константу-имя или метод строки (Е-2); «содержащий» не определено (В-5) |

- **В-1.** Треб. 5, ветка `ok` при `http_status None` и `verdict` не
  `unknown` (база красная или без конвейеров) — без критерия. Мутация
  «непустой `reason` → `skip`» проходит AC-10 (`green`, `reason` пуст) и
  AC-11 (`verdict` по умолчанию `unknown`).
- **В-2.** AC-9 не требует, чтобы `gh` был «найден» (`shutil.which`):
  иначе критерий пуст на main.
- **В-3.** AC-6 покрывает две формы перезапуска из семи, названных в
  треб. 9.
- **В-4.** AC-3/AC-4 задают номер правила подстрокой «`1`», без формы
  («правило 1»), и не запрещают упоминать в AC-4 правило 2.
- **В-5.** AC-15: «литерал, содержащий `github`…» — это равенство или
  подстрока? При подстроке сторож краснеет на законном
  `".gitlab-ci.yml" in no_paths` (треб. 8) и на `tok.kind == "operator"`
  в разборщике `if` (треб. 6); при равенстве — нет. Автор теста выберет
  сам.

## Зоны
- Зоны SPEC совпадают с ТЗ:12; `docs/codebase-map.md` — общая зона
  (`orchestrator/config.py`, `COMMON_ZONES`). Защищённых путей задача не
  трогает, песочница ролей не расширяется.
- `orchestrator/doctor/__init__.py` вне зон — коллаборанты фасада (`forge`,
  `targets`, `gitcmd`, `project_profile`) уже есть, новых треб. 1–13 не
  требуют. Исключение — разбор YAML (Б-2): `yamlmini.py` вне зон, и
  расширить общий разбор под `.gitlab-ci.yml` нельзя.
- `forge.py`/`gitlab_adapter.py` открыты под поле и проведение кода —
  этого хватает для треб. 4.

## Матрица неослабления
Раздела «Меняемое поведение» в SPEC нет и не нужно: строки
`project-*-<имя>` записи GitLab существующие тесты не утверждают
(`tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py` и
`tests/test_ci_actions_fallback.py` берут записи без `forge` — путь
GitHub, `ci_by_pipeline` для них ложно, `forge.py:196-197`).

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `check_ci_token` для GitLab | `fail` при недоступности CI токену, `project_checks.py:341-345` | да, на конвейерах GitLab | AC-11 (+ В-1) | держать; добавить случай `verdict none` |
| `check_project_token` для GitLab | `warn` при совпадении с токеном `gh` (triggers №24), `project_checks.py:239-243` | нет для GitLab | не покрыто заменой; AC-13 требует назвать, что сверка не делалась | разрешено ТЗ:39 прямо; токен GitLab с токеном `gh` (GitHub) и сейчас совпасть по смыслу не может — не ослабление |
| `check_base_protection` для GitLab | информационная `skip`/`ok`, `project_checks.py:176-208` | да | AC-1, AC-2 | держать |
| Строки GitHub-проектов | `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py`, `tests/test_ci_actions_fallback.py` | да | треб. 13, AC-15 + существующие тесты | держать |
| Сторож ac9 и `EXEMPT` | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:409-471` | да, не меняется | AC-15 + новый сторож по `project_checks.py` | держать (Е-2) |
| Запрет повторов (инвариант 41) | `docs/invariants.md:71`; `targets._rerun_argument` `targets.py:1114-1124` | да; добавляется строка `doctor` по `ci_job` | AC-6 (+ В-3) | держать |
| `forge-probe` без флагов | `tests/test_01m5wcxbr9k8cn586w1ap3zn6q_gitlab_doctor_probe.py:613-700` | да | существующие тесты, AC-14 | держать |
| Тексты `reason` адаптера | тесты `gitlab_adapter` | да | AC-12 «тексты прежние» | держать |

Строк «остаётся, не покрыто» без замены нет.

## Пути обхода гейтов
- **Е-1. Поле кода из текста `reason`.** ТЗ:34 и треб. 4 запрещают
  разбор текста, но адаптер может выставить `http_status =
  int(re.search(r"\((\d{3})\)", reason))`: каждый текст `_status_reason`
  несёт код (`gitlab_adapter.py:200-211`), и AC-12 на подменённом
  `transport` с неизменными текстами такую реализацию не отличит. Нужен
  случай, где код есть в `Reply.status`, а в `reason` его нет (подменённый
  `gitlab_adapter.request` → `Reply(403, reason="отказ")` → `http_status`
  403), либо AST-проверка, что `http_status` не выводится из `reason`.
- **Е-2. Выбор по хостингу мимо нового сторожа.** AC-15 ловит только
  сравнение с литералом. Проходят: словарь `{"gitlab": _gl}.get(
  doctor.forge.hosting(name))`, константа `_PIPELINE = ("gitlab",)` и
  `hosting in _PIPELINE`, `hosting.startswith("gitl")`. Треб. 1 («иных
  способов выбора нет») запрещает их словами. Надёжнее сторож, который
  запрещает в `project_checks.py` вообще читать значение хостинга
  (`forge.hosting`, `entry["forge"]`/`.get("forge")`, `IMPLEMENTATIONS`,
  `gitlab_adapter`) и `merge_gate`.
- **Е-3. «Файл не разобран → `skip`» как выход.** Без заданного
  подмножества YAML (Б-2) разборщик, понимающий только формы из AC-3/4/6,
  на настоящих файлах (якоря, `script: |`, `!reference`) честно даст
  `skip`. Строки 6 и 9 тогда по букве выполнены, а смысл (предупредить о
  ветке вне конвейера и о повторах, инвариант 41) — нет.
- **Е-4 (мелкое). Подмодули без слота.** Треб. 10: у записи без
  `token_slot` `gitcmd.hosting_token` даёт `(None, None)`
  (`gitcmd.py:139-141`), `ls-remote` идёт с авторизацией Оператора, и
  `ok` не доказывает «доступен по тому же слоту токена» (ТЗ:28). У
  слоистой записи `token_slot` обязателен (`targets.py:356`), у плоской —
  нет.

## Вердикт
**concerns** — SPEC годен в работу, отклонения решаются на гейте
уточнением критериев или решением Оператора.

1. Б-2 / Е-3: разбор `.gitlab-ci.yml` — разборщика в пульте нет,
   `yamlmini` (вне зон) блочные списки не разбирает
   (`orchestrator/yamlmini.py:16-20`); SPEC не говорит, где живёт разбор и
   какое подмножество YAML обязательно (треб. 6, 9). Решение Оператора:
   свой разборщик в `project_checks.py` либо зона `yamlmini.py`, и
   минимальное подмножество.
2. Е-1: AC-12 не отличает поле, заполненное разбором текста `reason`, от
   `Reply.status` (`orchestrator/gitlab_adapter.py:197-211`; SPEC треб. 4,
   AC-12).
3. Е-2 / В-5: новый сторож AC-15 обходится словарём, константой или
   методом строки, а «содержащий» не определено (SPEC треб. 1, AC-15).
4. В-2: AC-9 пуст без подменённого `shutil.which("gh")`
   (`orchestrator/doctor/project_checks.py:183-184`, `:212-213`).
5. В-1: у треб. 5 ветки `ok` при `verdict` `none`/`red` нет критерия
   (SPEC AC-11).
6. В-3: AC-6 проверяет 2 из 7 форм перезапуска треб. 9 (`default:`,
   `extends:`, `variables`, `-p`, установка плагина, `retry: 0` — без
   критерия).
7. В-4: номер правила в AC-3/AC-4 — подстрока «1» без формы.
8. Е-4: треб. 10 у записи без `token_slot` пробует с авторизацией
   Оператора (`orchestrator/gitcmd.py:139-141`).
9. Б-1 (мелкое): «единственное место сравнения `merge_gate`» — неверно,
   `orchestrator/targets.py:563`.
