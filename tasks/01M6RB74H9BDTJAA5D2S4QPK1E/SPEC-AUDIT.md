---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py; г) budget_usd 45 ≥ 45."
spec_sha: 7e7c818bf53d4a166b5b1d2674464e919039dfe9
schema_version: 5
---

# SPEC-AUDIT: Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new

Ветка задачи отстаёт от main (HEAD e3c56fd71, main 6bde2b9e6). SPEC ссылается
на строки main, поэтому факты сверены по `git show main:<путь>`.

## ТЗ и SPEC
- Требование ТЗ 1 → SPEC 1. Совпадает.
- Требование ТЗ 2 → SPEC 2, 3. Имя автора — `username`, а не `name`: так
  решил Оператор (гейт №1, решение 1). Копия файла — в `config.LOGS`,
  сверка блока целиком, функция возвращает причину без `sys.exit`: гейт №1,
  решение 4.
- Требование ТЗ 3 → SPEC 4. Сверяются имя и адрес (№1.1). Текст `fail`
  заменён решением №1.4. «Поля нет, API без адреса» — `warn` (№2.3).
  Пропуск в процессе роли — №1.4 и №2.3. Выбор GitLab через
  `ci_by_pipeline` — №2.4.
- Требование ТЗ 4 → SPEC 5. Добавлен путь `epic draft promote` (№2.2).
  Отказ идёт после `unsupported_reason` (№1.4).
- Требования ТЗ 5 и 6 (сверка в `_push_plan`) сняты решением №1.3 и
  перенесены в «Не входит» и требование 7. Это согласовано.
- Мандат ANSWER-1/2 в SPEC 6 сохранён, но им не пользуются (решение №2.4).
  Расхождения нет: мандат разрешает правку, не обязывает к ней.
- Причина отказа записи и её триггер (пробельный `username`) взяты из
  решений №2.1 и №3.1. Записка о сдвиге строк — из №3.2.
- В SPEC нет требований сверх ТЗ и решений Оператора. Противоречий между
  решениями Оператора не нашёл.

## Факты против кода
Все утверждения сверены по main, все подтвердились:
- `forge.TokenUser` — `orchestrator/forge.py:96-98`: поля `username` и
  `reason`. `forge.token_user` — `:452-453`, диспетчер `_call`.
- `gitlab_adapter.token_user` — `orchestrator/gitlab_adapter.py:579-586`.
  Строка `:584` проверяет только `isinstance(username, str)`, так что
  `"   "` проходит (решение №3.1 верно). У GitHub реализации `token_user`
  нет: «не реализовано для github» закрепляет
  `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py:936-951`.
- `targets._check_delivery` — `orchestrator/targets.py:715-720`: при
  пустом или пробельном значении (`v.strip()`) отказ
  «нужно {name, email} — обе непустые строки».
- `projects.py` на main:
  - `:380` — `BLOCK_PATHS` с `machine.commit_author`;
  - `:451-475` — `_target_set_load` (`sys.exit`, комментарий слоя `:473`);
  - `:487-493` — `_rendered`;
  - `:496-513` — `_target_set_write`: `sys.exit`, копия, журнал
    `store.journal`;
  - `:656-674` — `_block_keys` принимает `["machine","commit_author"]`;
  - `:894-898` — сверка одного листа;
  - `:905-932` — `_target_set_block_mismatches`, сводится к
    `_merge_mismatches` (`:965`) → `targets.merge_local`;
  - `:991` — `_backup_copy` в `config.LOGS`.
- `gitcmd.commit_author`, `pult_identity`, `pult_identity_args` —
  `orchestrator/gitcmd.py:559`, `:567`, `:572`. `_author_check_refusal` —
  `:625-660`, отказ при `username != name` (`:657-659`).
- `project_checks.py:48-51` — `by_pipeline = doctor.forge.ci_by_pipeline(name)`.
  `:53-66` — `ROLE_SKIP` для clone, push, token, ci-token.
- `catalog.cmd_new` — `orchestrator/catalog.py:775`; `unsupported_reason` —
  `:856-858`. `epics.py:796` зовёт `catalog.cmd_new` напрямую.
- `doctor/cli.py:312-341`: починки идут до `all_checks`. `:352-355`:
  `sys.exit(1)` при любом `fail`.
- Поведение песочницы, от которого зависит требование 6:
  `isolate_keychain_and_role` (`tests/sandbox.py:676-696`) ставит
  `refused_gitlab_transport` (`:668-673`). Это `URLError` без повтора, то
  есть сторож даёт `warn`. Решение №2.4 этим подтверждается.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `commit_email` не берётся из ответа; нет запасного `email`; `name` не заполняется. До кода — красный: у `TokenUser` нет полей. Часть про «прочие адаптеры» у GitHub пуста (`token_user` нет); добавление реализации ловит существующий `github_mr_units.py:936`. |
| AC-2 | да | В `name` пишется `name` вместо `username` (они различны); нет копии в `config.LOGS`; нет строки журнала; повтор переписывает файл или дописывает журнал. До кода — красный: поля в слое нет. |
| AC-3 | да | Нет запасного `email`. Запись идёт при отказе API. Адаптер или автопоиск отбраковывает пробельный `username` раньше сверки, и причина уже не «сверка до записи не прошла». `sys.exit` обрывает `doctor`, и строк проверок после отказа нет. До кода — красный по строке причины. |
| AC-4 | да | `ok` только по адресу без имени (ловит ветка «адрес совпадает, имя = `name`»). `--fix` перезаписывает расхождение. Поле не задано и API без адреса — `fail` вместо `warn`. В роли зовётся `token_user` (шпион). Утечка токена (проверка по фикстурному токену). До кода — красный: строки проверки нет. |
| AC-5 | да | Отказ стоит в обёртке `artel.py`, а не в `cmd_new`: `epic draft promote` заводит задачу. Отказ после создания ссылки документов. Проверка стоит до `unsupported_reason`, и текст отказа неподдержанного проекта меняется. До кода — красный: задача заводится, текста отказа нет. Тест обязан сверять текст отказа: одно «задачи нет» в красной фазе может пройти по посторонней причине. |
| AC-6 | да | `warn` трактуется как отказ; предупреждения в выводе нет. До кода — красный по предупреждению. |

Опасных форм нет: красная фаза не порождает рекурсии и процессов git.
Ответы API подменяются, в сеть тесты не ходят (транспорт песочницы
отказывает), отправки в настоящий origin нет.

## Зоны
- Зоны SPEC: `forge.py`, `gitlab_adapter.py`, `doctor/project_checks.py`,
  `doctor/cli.py`, `projects.py`, `catalog.py`, `docs/codebase-map.md`,
  `tests/`. Они покрывают все требования: функция записи без `sys.exit` —
  в `projects.py`, отказ — в `catalog.py`.
- `orchestrator/gitcmd.py` справедливо вне зон (решение №1.3). Чтение
  `forge.token_user` правки `gitcmd.py` не требует. `epics.py` правка не
  нужна (отказ в `cmd_new`).
- Защищённых путей (`config.PROTECTED_PATHS`) зоны не трогают. Песочница
  ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `forge.TokenUser`: новые поля | позиционная сборка `TokenUser("probe-user")` — `tests/test_01m6ezxvfgh5z2876xwmqg35fp_forge_probe_ref_sha.py:82` | да, если поля идут после `username` с дефолтом `None` | тот же тест | ок |
| `gitlab_adapter.token_user` | единственный вызов `GET /user` — `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:1623`; набор пар `ALLOWED_PAIRS` — `tests/test_forge_gitlab_request.py:174-187` | да: адрес берётся из того же ответа `GET /user` (требование 1) | те же тесты | ок |
| `project_entry_checks`: новая строка | точный список 8 строк для github и артели — `tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:813`, `:819` | да: строка есть только у GitLab (требование 4), в `_names()` не входит | те же тесты | ок |
| `project_entry_checks` без `token_slot` в роли | `tests/test_doctor_gitlab_ci_file.py:153-172` | да: условие «`forge: gitlab` и `token_slot`» и пропуск в роли | тот же тест | ок |
| сравнение `forge` с литералом | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:491` (`test_ac9`) | да: `ci_by_pipeline` (требование 4) | тот же тест | ок |
| `cmd_new`: новый отказ | отказ неподдержанного проекта — `unsupported_project.py:199`, `:399`; `pair_support.py:134-141`, `:161`; `tests/test_epic_draft_promote_unsupported_project.py:90-97` | да: проверка после `unsupported_reason`, в песочнице `warn` | те же тесты, без правки | ок |
| `doctor` для GitLab с ответом API | `tests/test_01m5wcxbr9k8cn586w1ap3zn6q_gitlab_doctor_probe.py:298-325` (утечка токена; строки `warn` по сроку токена) | да: новая строка `fail` в обоих прогонах, отбор строк по сроку её не берёт; значения токена в вывод не идут | тот же тест | ок |
| хелперы `target-set` (`projects.py:451-513`) при выделении функции без `sys.exit` | тексты отказов CLI `target-set` — тесты `target-set` | да: тексты CLI не меняются (требование 3 добавляет функцию) | существующие тесты `target-set` | ок |

Раздела «Меняемое поведение» в SPEC нет и не нужно: ни одно утверждение
существующих тестов не меняется (требование 6). Поиск по `tests/` на main
сломанных существующих тестов не нашёл.

## Пути обхода гейтов
- Буквального обхода не нашёл. Отказ ставится в `cmd_new`, так что его не
  обходит ни `epic draft promote`, ни `canary_drive.py:54`. Гейт зон
  держит неизменность `gitcmd.py`. Требование 6 без правки тестов держат
  гейт неослабления и требование зелёного набора.
- Наблюдение, не отклонение (вне ТЗ). `catalog.spawn_subtask`
  (`orchestrator/catalog.py:1082`) заводит части деления через
  `_new_task_row`, в обход `cmd_new`. Так он уже обходит и
  `unsupported_reason`. Родитель прошёл сторож при `new`; смена токена
  между `new` и делением сторожем `new` не ловится, её увидит `doctor`.
- Наблюдение, не отклонение. Поле задано, API ответил без адреса →
  `warn`, даже если имя расходится с `username`. Это буквально по
  требованию ТЗ 3 («API не дал адреса» — `warn`).

## Вердикт
`pass` — отклонений нет. Все утверждения SPEC о коде подтвердились по
main. Каждое требование ТЗ отражено в SPEC либо снято решением Оператора,
у каждого AC есть ловимая мутация и красная фаза без опасных форм.
Существующие тесты не краснеют без правки. Разработчику стоит учесть
ловушки из матрицы:
- новую строку не включать в `_names()`;
- поля `TokenUser` ставить после `username`;
- адрес брать только из одного `GET /user`;
- проверку в `cmd_new` ставить после `unsupported_reason`.
