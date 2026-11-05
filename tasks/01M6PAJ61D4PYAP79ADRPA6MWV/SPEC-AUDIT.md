---
task: 01M6PAJ61D4PYAP79ADRPA6MWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py; в) пути-признаки (гейты): orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/two_sided.py; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0023.
spec_sha: e06c94d386dcdd4516a1559fdc9448885520ae97
schema_version: 5
---

# SPEC-AUDIT: Ядро раннера compose

## ТЗ и SPEC

- Перенос сверен механически (difflib) с SPEC родителя
  (`refs/artifacts/01M6P22XBCQS49HE92YGAB25N9`): требования 1–11 и 16–17 (здесь
  12–13), AC-1…AC-16 и AC-22 (здесь AC-17) совпадают дословно, кроме трёх мест.
  (1) Из требования 6 (SPEC.md:164-169) убраны вызовы `doctor` и
  `context inspect`. (2) Из требования 13 (SPEC.md:219-247) убраны ответы
  `ps`/`network ls`/`version`/`context inspect`, `runner.DOCKER_CALL_TIMEOUT_SEC`,
  форма тестов «забытых стендов» и `runner.compose_role_dir()`.
  (3) «требование 14» заменено на «часть 2». Это ровно то, что ТЗ относит к
  части 2. Зоны, «только чтение» и «Не входит» совпадают с ТЗ и с подразделом
  «Деление → Ядро раннера compose» родителя.
- ANSWER-1 родителя (вопросы 1, 2, 4, 5 и часть вопроса 3 о процессе роли)
  отражён: в требованиях 6, 1–2, 5, 7. Вопрос 5 (порог версии в `doctor`)
  относится к части 2. Потерь нет.
- Требований сверх ТЗ и ANSWER нет.
- Следствие переноса: при удалении `runner.DOCKER_CALL_TIMEOUT_SEC` у вызова
  `config` места не осталось никакого предела. А требование 13
  (SPEC.md:223-224) по-прежнему велит подменённому `docker` отвечать на `config`
  «в том числе зависанием и ненулевым кодом». Поведение пульта при таком ответе
  не задаёт ни одно требование и ни один AC. В родителе пробел был тот же, но
  там предел вызова `docker` хотя бы был назван (для `doctor`/`role_env`).
  См. вердикт, п. 2.

## Факты против кода

Подтвердилось (рабочий каталог, 54fe44ebb):
- `orchestrator/acceptance.py`: `_own` :121, `_OWN_SYSTEM_PATH_DIRS` :156,
  `_own_path` :159, `_own_env` :189, `_link_deps` :583 (исключение через
  `_exclude_pattern` :605), `_report_env` :626, `_report_argv` :736, `_report_run` :806,
  `_report_suite_result_key` :3069; `run_plank` :2042, без раскладки планка
  берётся из `tasks/<id>/acceptance_tests` :2068; `_plank_plan`/`_component_layout`
  :1270-1301.
- `orchestrator/targets.py`: `PROFILE_FIELDS` :56, `PROFILE_OPTIONAL` :76-77,
  `PROFILE_RUNNERS` :83, `PROFILE_OWN_RUNNER_ONLY` :85, `machine.path` только при
  `pytest-own` :755-773, `_with_env` (PATH в `env`) :776-793, `_check_rerun_ban` :1194
  (условие `_is_pytest_command(fields.get("command"))` :1199), правило `layers`
  :1237-1239.
- `orchestrator/plank_layout.py:41-47` `layout_mode`; `orchestrator/runner.py:1364-1381`
  `in_role_environment`; `orchestrator/lease.py:399` `process_alive`;
  `orchestrator/appendix_tree.py:259-261` (у не-артели дерево прогона — сама рабочая копия).
- `project_profile.reported` (`project_profile.py:511-521`) сейчас истинен только у
  компонента или `pytest-own`. `test_integrity._own_profile`
  (`advance_gates/test_integrity.py:1651-1655`) у не-`pytest-own` даёт `None`, и
  двусторонний прогон пошёл бы раннером пульта. Обе правки в зонах (AC-10).
- Потребители «только чтение» с правкой зон совместимы:
  - `suite_run._profile_command` берёт профиль при `report` (`suite_run.py:340-349`);
  - `_extra_flags` у профиля с отчётом пуст (`suite_run.py:106-109`);
  - `two_sided._run_side` ветвится по `acceptance.reported`
    (`two_sided.py:289-291`);
  - `outcome_integrity` зовёт `acceptance.report_run`
    (`outcome_integrity.py:445, 736`);
  - `mutation_run._profile_refusal` отказывает любому раннеру, кроме
    `pult-pytest` (`mutation_run.py:379-395`). Это согласуется с «Не входит».
- Деревья сторон и базы — `git worktree add` (`suite_run.py:568`,
  `two_sided.py:466`), поэтому `git ls-files --error-unmatch` в них осмыслен.

Не подтвердилось или неполно:
- **Умолчание `command` вне зон.** `repo_context.profile_of`
  (`orchestrator/repo_context.py:183-188`, вне зон) отказывает единственному
  компоненту без подполя не из `PROFILE_OPTIONAL` («нет подполя 'command'»). Тот же
  отказ — в `project_profile.py:370-377`. `Profile.from_values` берёт
  `values["command"]` без умолчания (`project_profile.py:132`). Через
  `project_profile.decide` (:205) это задевает `plank-run`, `suite-run` и все гейты.
  - Внести `command` в `PROFILE_OPTIONAL` нельзя: сломается «`pytest-own` без
    `command` — отказ» (AC-2) у компонентов, где обязательность держит именно эта
    проверка.
  - Путь в зонах есть — подставлять `["pytest"]` в копию записи в `targets.load`
    (как `_with_long_lived_pairs`, `targets.py:268-272`). Но SPEC этот канал не
    называет (SPEC.md:64-66 говорит только «без неё — `["pytest"]`»).
  - Естественная правка `repo_context.py` упрётся в гейт зон.
- Утверждения о Docker CLI проверить опытом не удалось: программы `docker` в
  окружении шага нет (`which docker` — not found). Без опыта остаются:
  - форма вывода `config --format json` (SPEC сам пометил «опытом не проверено»,
    SPEC.md:119-123);
  - появляется ли неявная `default` в выводе `config`;
  - вид `name:` у сетей и томов в выводе.

## Проверяемость критериев

Колонка «Тест до кода» отвечает на вопрос, что сделает тест в красной фазе, без
механизма задачи.

| Критерий | Проверяем | Ловимая мутация | Тест до кода |
|---|---|---|---|
| AC-1 | да | `compose` не в `PROFILE_RUNNERS`; умолчание `command` не подставлено; `machine.path` при `compose` отказан (`targets.py:757`) | красный по `TargetsError`, безопасен |
| AC-2 | частично | ловит каждое перечисленное правило. **Не ловит:** снятую обязательность `compose_file`/`compose_service`/`compose_env_file`/`compose_env_template`/`compose_mount` (требование 1, SPEC.md:48-60) — отсутствия поля AC не проверяет; `compose_mount` с двумя парами или без `:` («ровно одна пара»); `compose_up_down_sec` ≤ 0 | красный, безопасен |
| AC-3 | да | argv без `--project-directory`/`-w`/`--rm`; отчёт вне смонтированного каталога; итог по коду выхода, а не по отчёту | красный: `docker` не зовётся |
| AC-4 | да | `ports` не сняты; `default` без `internal`; нет метки; шаблон не перезаписан | красный |
| AC-5 | да | одно из правил сокета снято; сверка `realpath` без разрешения ссылки; `tcp://` пропущен | красный, безопасен (сокет — файл песочницы) |
| AC-6 | да | префикс сверяется без `_` (ловит `<имя>2_db`); `name:` тома не проверен | красный |
| AC-7 | да | путь не переведён; путь вне монтирования прошёл | красный |
| AC-8 | частично | `down` только на зелёном; нет `kill` на таймауте; нет `--rmi local`. **Не ловит:** `down` при «снятии группы процессов» (требование 8, SPEC.md:199), и канал (обработчик SIGTERM в библиотечном модуле при `auto.py:690`, запас 3 с `liveness.GROUP_TERMINATE_GRACE_SEC`) не задан | красный; зависание — `exec sleep <n>`, ограничено |
| AC-9 | да | постоянный id прогона или id от секунд | красный |
| AC-10 | да | `_own_profile` не расширен — в argv `-p <плагин>`, в окружении `PYTHONPATH` | красный |
| AC-11 | да | `os.environ` целиком; `PATH` вызывающего; `config` без чистого окружения | красный. Оговорка: тест, запущенный из шага роли (`ARTEL_ROLE` задан), попадёт в ветку требования 7, если не снимет `ARTEL_ROLE`; SPEC эту форму не задаёт |
| AC-12 | да | откат на `~/.docker` пульта; фоновый вызов без `ARTEL_ROLE` не распознан | красный |
| AC-13 | да | удаление всего `.artel-report`; нет `info/exclude`; копирование до проверки `ls-files` | красный, git — вымышленный репозиторий песочницы |
| AC-14 | да | слагаемое не добавлено; поле записи проигнорировано | красный. Практичен только с подменой малых пределов в `config` (не запрещено) |
| AC-15 | да | поле или константа перекрытия не в ключе | красный |
| AC-16 | да | поля `compose_*` вписаны в ключ безусловно — ломается и `tests/test_report_argv_rerun_ban.py:98-130` | зелёный с рождения (страж регрессии), безопасен |
| AC-17 | да | тест без пропуска при `CI`, без `pull_policy: never`, без проверки образа | пропуск. Собственная проба теста (`docker info`/`image inspect`) без предела времени не оговорена |

Пробел вне AC: исход пульта на ответ `config` с ненулевым кодом, не-JSON или
зависанием не задан ни одним требованием, хотя требование 13 (SPEC.md:223-224)
велит подменённому `docker` так отвечать. Предел этого вызова тоже не задан. Тест
на зависание `config` либо выдумает ожидание, либо будет ждать до
`ACCEPTANCE_TIMEOUT_SEC` + `COMPOSE_UP_DOWN_SEC` (600 с), если предел места
относят и к `config`. Не сказано и то, зовётся ли `down` после провала `config`.

## Зоны

- Требования 1–11 укладываются в `targets.py`, `project_profile.py`,
  `acceptance.py`, `two_sided.py`, `test_integrity.py`, `config.py`
  (`COMPOSE_UP_DOWN_SEC`) — с одной оговоркой: умолчание `command` единственного
  компонента проходит через `repo_context.profile_of` (`repo_context.py:183-188`),
  а `repo_context.py` вне зон. Выполнимо в зонах только подстановкой в
  `targets.load`. SPEC канал не называет (см. «Факты против кода»).
- Защищённые пути (`config.PROTECTED_PATHS`, `config.py:795-801`) требования не
  трогают; `targets.yaml` правке не подлежит.
- Песочница ролей не расширяется: `runner.py` и `stack.py` — только чтение;
  окружение роли — часть 2.
- `docs/codebase-map.md` в зонах — требование 12 выполнимо.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `workdir`/`env` только при `pytest-own` | `targets.py:1096-1103`, `:1258-1265`; `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py:209-236` | да для `pult-pytest`; у `compose` `workdir` обязателен, `env` из `description` — отказ | AC-1, AC-2; прежний тест (только `pult-pytest`) зелёный без правки | ок |
| `machine.path` только при `pytest-own` | `targets.py:755-773`; `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py:629-656` | да для прочих; у `compose` — только `PATH` вызова `docker` | AC-1, AC-11 | ок |
| обязательность `command` | `targets.py:1087-1092`; `repo_context.py:183-188`; `project_profile.py:370-377` | да для прочих раннеров | AC-2 («`pytest-own` без `command` — отказ») | ок при условии: канал умолчания не трогает `PROFILE_OPTIONAL` (вердикт, п. 1) |
| запрет повторов и правило `layers` у команды pytest | `targets.py:1194-1222`, `:1237-1239` | да; у `compose` без `command` — как у pytest | AC-2 (`--reruns` в `report_args`) | ок |
| состав ключа итога с отчётом | `acceptance.py:3083-3096`; `tests/test_report_argv_rerun_ban.py:98-130` | да при добавлении полей только у `compose` | AC-15, AC-16; прежний тест | ок при условии: поля `compose_*` в ключе только у `compose` |
| чистое окружение прогона (`HOME` пульта не уходит) | `acceptance.py:189-211` | да, строже: окружение `docker` без `PATH` вызывающего | AC-11, AC-12 | ок |
| двусторонний прогон по профилю | `test_integrity.py:1651-1655`, `two_sided.py:289-303` | да; `compose` — веткой отчёта | AC-10 | ок |
| закрытые имена `acceptance` вне модуля | `tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py:331-373` | да, помощники для части 2 публичные | прежний тест | ок |
| сокет Docker не передаётся в контейнеры (ADR-0023, поправка 05.11, п. 2, `docs/adr/0023-role-step-sandbox.md:1309-1311`) | нового кода нет | частично: правило требования 5 смотрит только на источники bind-монтирований сервисов | AC-5. Не покрыты именованный том `driver_opts` с `o: bind` и `secrets`/`configs` с `file:` (см. «Пути обхода») | не ок без требования-замены (вердикт, п. 3) |

Существующих тестов, которые сломаются при правке «только у `compose`», поиском
не нашлось. Искал по `PROFILE_RUNNERS`, `PROFILE_FIELDS`, `PROFILE_OPTIONAL`,
`PROFILE_OWN_RUNNER_ONLY`, `_own_profile`, `_report_suite_result_key` и текстам
«допустим(о) только при» в `tests/`. `tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py:269-277`
берёт перечень полей динамически. Докстринг
`tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py:188` («вне
`pult-pytest | pytest-own`») устареет, но проверяемые там значения `compose` не
включают. Отсутствие раздела «Меняемое поведение» (SPEC.md:324) по коду обосновано.

## Пути обхода гейтов

1. **Сокет Docker через именованный том.** Том верхнего уровня с
   `driver: local`, `driver_opts: {type: none, o: bind, device: /var/run}` и
   монтирование `type: volume` в сервис отдают сокет контейнеру. Правило
   требования 5 (SPEC.md:136-146) смотрит только на «источник bind-монтирования»,
   поэтому SPEC можно выполнить буквально и нарушить ADR-0023, п. 2 («сокет Docker в
   контейнеры не передаётся»).
2. **Сокет Docker через `secrets`/`configs` с `file:`.** Compose монтирует их в
   `/run/secrets/…` bind-монтированием из `file:`. Источник не в `volumes` сервиса,
   и правило требования 5 его не видит.
3. **Сокет из контекста Docker.** Вне процесса роли `DOCKER_HOST` обычно не задан
   (Docker Desktop адресует службу контекстом). Сверка `realpath` берёт только
   `DOCKER_HOST` и `/var/run/docker.sock`, «если он есть» (SPEC.md:142-146). Если
   ссылки `/var/run/docker.sock` нет, настоящий сокет контекста (например,
   `~/.docker/run/docker.sock`) и его каталоги не сверяются. Опытом не проверено:
   `docker` в окружении шага нет.
4. **Плоская запись `compose` в слое репозитория.** Отказ по `env` задан только
   для раздела `description` (SPEC.md:82-85). Плоская запись
   (`targets._repo_entries`, `targets.py:227-234`; тесты пишут такие записи) с
   `env` пройдёт: после сведения `env.PATH` неотличим от `machine.path`. Риск
   низкий: `targets.yaml` защищён.

## Вердикт

**concerns**. Отклонения — на решение Оператора на гейте (ТЗ требует переноса
дословно, поэтому дополнения — решением гейта, а не правкой аналитика):

1. **Канал умолчания `command` не назван; естественный путь — вне зон.**
   - Где: SPEC.md:64-66; `orchestrator/repo_context.py:183-188` (вне зон),
     `orchestrator/project_profile.py:132`, `:370-377`.
   - Что предложить: назвать канал — подстановку `["pytest"]` в копию записи
     `targets.load` (рядом с `_with_long_lived_pairs`, `targets.py:268-272`) — либо
     расширить зоны на `orchestrator/repo_context.py`.
2. **Исход и предел вызова `config` не заданы.**
   - Где: SPEC.md:113-131, :223-224.
   - Что предложить: требование и AC на ненулевой код, не-JSON и зависание
     `config` (отказ запуска с текстом вызова, предел вызова, `up`/`run` не зовутся,
     зовётся ли `down`).
3. **Правило сокета Docker обходится.**
   - Где: SPEC.md:136-146; `docs/adr/0023-role-step-sandbox.md:1309-1311`.
   - Обход: именованный том с `driver_opts` `o: bind`, `secrets`/`configs` с
     `file:`, сокет текущего контекста без `DOCKER_HOST`.
   - Что предложить: отказ и на эти формы, либо явное решение Оператора, что риск
     принят.
4. **AC-2 не проверяет обязательность полей `compose_*`** и форму «ровно одна
   пара» `compose_mount`.
   - Где: SPEC.md:48-60, :253.
   - Мутация «поле стало необязательным» проходит все AC.
5. **«Снятие группы процессов» без AC и без канала.**
   - Где: требование 8, SPEC.md:199; AC-8, SPEC.md:265.
   - Канал: обработчик SIGTERM в `acceptance` при своих обработчиках `auto.py:690`,
     `:1868`; запас 3 с у `liveness.GROUP_TERMINATE_GRACE_SEC`
     (`liveness.py:50`) против `down` с `--rmi local`.
   - Что предложить: снять пункт до части 2 (остатки ловит `doctor`) либо задать
     канал и критерий.
6. **Мелкое.**
   - Форма тестов AC-11 не велит снимать `ARTEL_ROLE` у теста, запущенного из шага
     роли.
   - Пробе Docker в необязательных тестах (AC-17) не задан предел времени.
   - Отказ по `env` у плоской записи `compose` слоя репозитория не задан
     (SPEC.md:82-85).
   - Отсутствие `compose_env_template` в дереве прогона (базы, стороны) не имеет
     заданного отказа (SPEC.md:117-118).
