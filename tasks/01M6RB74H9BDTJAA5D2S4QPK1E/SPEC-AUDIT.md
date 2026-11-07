---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py; г) budget_usd 45 ≥ 45
spec_sha: 5e078eb2f6be8b0cb01207eb35947820c195d02d
schema_version: 5
---

# SPEC-AUDIT: Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new

## ТЗ и SPEC
Сверено в обе стороны с ТЗ, ANSWER-1, ANSWER-2 и решениями Оператора
№1.1–№1.4 и №2.1–№2.4 на гейте SPEC.

- ТЗ «Требуется» 1 → SPEC тр. 1. Совпадает.
- ТЗ 2 (`name: <name пользователя токена>`) → SPEC тр. 2
  (`name: <username>`). Смена законна по решению №1.1.
- ТЗ 2 (копия, сверка, журнал путём `target-set`) → SPEC тр. 3. Уточнения
  взяты из решений №1.4 и №2.1: функция без `sys.exit`, копия в
  `config.LOGS`, сверка блока целиком, причина «сверка до записи не
  прошла».
- ТЗ 3 → SPEC тр. 4. Сверка имени взята из решения №1.1, текст `fail` —
  из №1.4. Деление `fail`/`warn` — из №1.2 и №2.3. Пропуск в роли — из
  №1.4 и №2.3. Литерал запрещён решением №2.4.
- ТЗ 4 → SPEC тр. 5. Порядок после `unsupported_reason` — решение №1.4,
  путь `epic draft promote` — решение №2.2.
- ТЗ 5 и 6 → SPEC тр. 7 и «Не входит». ТЗ 5 снят решением №1.3. Критерий
  «gitcmd.py не меняется» снят решением №2.3: свойство держит гейт зон.
- ТЗ «существующие тесты зелёные без правки» → SPEC тр. 6. Мандат ANSWER-2
  сохранён, но им запрещено пользоваться (решение №2.4).
- Зоны SPEC = зоны ТЗ без `orchestrator/gitcmd.py` (решение №1.3).

Требований SPEC вне ТЗ и решений нет. Решения Оператора между собой не
противоречат. Решение №1.2 (мандат) и решение №2.4 («не пользоваться») —
уточнение, не спор.

## Факты против кода
Подтвердилось по рабочему каталогу:
- `orchestrator/targets.py:715-720`: `commit_author` — `{name, email}`, обе
  строки непустые после `strip()`.
- `orchestrator/gitcmd.py:559` `commit_author`, `:572`
  `pult_identity_args`, `:625` `_author_check_refusal` (отказ при
  `username != name`). Решение №1.1 верно.
- `orchestrator/forge.py:96`: `TokenUser(username, reason)`.
- `orchestrator/gitlab_adapter.py:579-586`: `token_user` проверяет только,
  что `username` — строка (`:583`), и ничего больше не читает.
- `orchestrator/doctor/project_checks.py:51`:
  `by_pipeline = doctor.forge.ci_by_pipeline(name)`; `:53-66` — `ROLE_SKIP`
  у строк проекта в роли; `:31-34` — `_names`.
- `orchestrator/forge.py:395-399`: `ci_by_pipeline(target)` принимает имя
  проекта. Форма из решения №2.4 верна.
- `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:491` —
  `test_ac9_no_support_literals_outside_targets`. Он ловит
  `forge == 'gitlab'` (образец `:512`).
- `orchestrator/epics.py:796`: `cmd_draft_promote` зовёт `catalog.cmd_new`
  напрямую. До вызова ничего не пишет (`:785-795`): отказ из `cmd_new` не
  оставляет следа promote.
- `orchestrator/catalog.py:855-857`: `unsupported_reason` в `cmd_new` до
  `_new_refs`, БД, ТЗ, id и ссылки документов.
- `orchestrator/projects.py:889-893` — сверка одного листа; `:900-926` —
  `_target_set_block_mismatches`; `:986` — `_backup_copy` в `config.LOGS`;
  `:451-515` — `sys.exit` во всех отказах `_target_set_load`, `_rendered`,
  `_target_set_write`; `:473` — отказ из-за строки-комментария.
- `orchestrator/doctor/cli.py:312-341`: починки `--fix` идут до
  `all_checks`; `:352-355` — `sys.exit(1)` при любом `fail`. Решение
  №2.1 верно, и порядок строк AC-3 достижим без перестановки кода.

Неточность в решении Оператора, не в SPEC (Ф-1): решение №1.4 называет
копию `orchestrator/projects.py:996`. На деле `def _backup_copy` стоит на
`:986`, как и пишет SPEC. На суть решения не влияет.

Опыт (временный процесс, без записи на диск): `projects._render` пишет
`name: "   "` в кавычках, а `yamlmini.mapping` читает его обратно как
`'   '`. Это опора для В-1 ниже.

Утверждений о поведении git или ОС в SPEC нет. Поведение GitLab
(`commit_email` в `GET /user`) взято из опыта Оператора 06.11. Тесты его
подменяют.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | нет запасного `email`; `name` подставлен в `username`; поля заполнены у GitHub. До кода: у `TokenUser` нет полей → красный, без побочных эффектов |
| AC-2 | да | в `name` пишется `name`, а не `username`; нет копии в `config.LOGS`; нет строки журнала; повтор переписывает файл или плодит копии. До кода: слой не меняется → красный |
| AC-3 | частично (В-1) | API отказал, а слой переписан; `sys.exit` обрывает `doctor` до `all_checks`. Ветка «сверка до записи не прошла» — см. В-1 |
| AC-4 | да | сверяется только адрес; `--fix` перезаписывает несовпадение; в тексте нет обоих значений; `test-token-<слот>` (`tests/sandbox.py:657-660`) в выводе; в роли нет `skip` или идёт вызов API. Безопасная форма «не зовёт `token_user`» — счётчик вызовов подменённого транспорта: он ловит и `forge.token_user`, и прямой `gitlab_adapter.token_user` |
| AC-5 | да | отказ положен в `new_cli_target`, а не в `cmd_new` (ловит путь promote); отказ после строки `tasks` или ссылки документов; отказ раньше `unsupported_reason` (меняется текст у неподдержанного). До кода: задача заводится → красный |
| AC-6 | да | `warn` приравнен к `fail`; предупреждение не печатается |

Красная фаза безопасна: рекурсии, хуков и порождения процессов критерии
не требуют. API подменяется транспортом, а песочница по умолчанию
отказывает в HTTP (`tests/sandbox.py:668-696`). Тестам AC-2 и AC-3 через
полный `cmd_doctor(fix=True)` стоит заранее завести каталог клона
(`_fix_project_clones`, `orchestrator/doctor/cli.py:318`), как это
делает `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:176`.

В-1 (AC-3). Решение №2.1 задало текст причины, но не задало, чем отказ
вызвать. При верной сборке текста сверка по построению проходит.
Внешний триггер есть, хотя SPEC его не называет: ответ `GET /user` с
`username` из одних пробелов. Тогда `token_user` его примет
(`gitlab_adapter.py:583`), а `_render` запишет его в кавычках (проверено
опытом). Дальше `_merge_mismatches` → `targets.merge_local` →
`_check_delivery` (`orchestrator/targets.py:517`, `:715-720`) отклонит
запись → «сверка до записи не прошла». Но и реализация, которая сверяет
ответ API заранее (пустое имя — «в ответе нет имени»), тоже честно
выполняет SPEC — и даёт другую причину. Без названного в критерии
триггера автор теста либо подменяет внутренний помощник (тогда тест
навязывает устройство, skills/escalation-rules.md), либо выбирает
триггер, на который SPEC не обязывает отвечать этой причиной. Стоит
назвать триггер в AC-3 (например, `username` из пробелов) или снять
ветку «отказ записи» с этой причиной из долгоживущего теста.

Примечание (не отклонение): AC-2 «в журнале — строка записи» не задаёт
актора и действие строки. Тест может проверить только, что появилась
новая строка журнала с `target=<проект>`. Сверять с `"target-set"` и
`"operator"` (`orchestrator/projects.py:513`) значило бы навязать
устройство.

## Зоны
- Тр. 1 → `forge.py`, `gitlab_adapter.py`. Тр. 2–4 →
  `doctor/project_checks.py`, `doctor/cli.py` (вход `--fix`, `:312-341`),
  `projects.py`. Тр. 5 → `catalog.py`. Тесты → `tests/`. Всё в зонах.
- `orchestrator/doctor/__init__.py` вне зон. Прочие `_fix_*` зовутся
  через него, но `cli.py` уже зовёт модуль напрямую
  (`doctor.project_checks.component_checks`, `cli.py:216`), так что
  новую починку можно звать так же.
- `orchestrator/epics.py` вне зон и не нужен: отказ идёт через
  `cmd_new` (`epics.py:796`).
- `gitcmd.py` вне зон, согласно тр. 7. Защищённых путей задача не
  трогает. Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `forge.TokenUser` — поля `name`, `commit_email` | `TokenUser("probe-user")` — tests/test_01m6ezxvfgh5z2876xwmqg35fp_forge_probe_ref_sha.py:82; `TokenUser(data["username"])` — orchestrator/gitlab_adapter.py:586 | да, если новые поля идут после `username` и имеют значение по умолчанию | тот же тест | ок |
| `gitlab_adapter.token_user` | один `GET /user`, повтор 5xx, причина — tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:1018-1085; tests/test_01m5wcxbr9k8cn586w1ap3zn6q_sandbox_no_http.py:154,176 | да: запрос прежний | те же тесты | ок |
| `project_entry_checks` — новая строка | точный список строк github и восемь строк `skip` артели — tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:813,819 | да: тр. 4 «строка только у GitLab», выбор через `ci_by_pipeline` (решение №2.4) | те же тесты | ок |
| `all_checks` — строка у GitLab | разность `warn` двух прогонов — tests/test_01m5wcxbr9k8cn586w1ap3zn6q_gitlab_doctor_probe.py:262-270 (`/user` без адреса, `:143-144`) | да: «нет адреса» — `warn` в обоих прогонах | тот же тест | ок |
| `cmd_new` — отказ по сторожу | `new` GitLab заводит задачу — tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:161, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:401; отказ неподдержанного прежним текстом — tests/test_epic_draft_promote_unsupported_project.py:60, tests/test_01m6n7cykdamakenx60cbk7vqx_pair_open.py:345 | да: песочница отказывает транспорту (tests/sandbox.py:692-696, :1643) → `warn` → задача заводится; утверждения — подстроки, не точный вывод; у неподдержанного отказ раньше сторожа | те же тесты без правки | ок |
| `test_ac9` — запрет литерала `forge` | tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:491 | да: тр. 4 требует `ci_by_pipeline` | тот же тест | ок |
| `gitcmd._push_plan`, `_author_check_refusal` | сверка автора до первой отправки — tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py:1404-1530 | да: файл не меняется | те же тесты; гейт зон | ок |
| `cmd_doctor(fix=True)` — новая починка | выводы `--fix` существующих тестов — записи артели и github | да: починка только для GitLab с `token_slot` без поля | те же тесты | ок |

Раздела «Меняемое поведение» в SPEC нет и не нужно: существующие
утверждения не меняются.

## Пути обхода гейтов
- Прошлые Е-1 (promote мимо обёртки) и Е-2 (`--fix` в роли) закрыты:
  тр. 5 и AC-5 называют `cmd_new` и `epic draft promote`, тр. 4 и AC-4 —
  поведение `--fix` в роли.
- Е-1 (продолжение В-1). Реализация может вовсе не сверять текст до
  записи. AC-3 поймает это только на триггере, который ведёт в
  `merge_local`, а SPEC его не называет.
- Обход через `warn` («API не ответил» → задача заводится) — осознанное
  решение №1.2, не отклонение.

## Вердикт
concerns. Возврат аналитику не нужен, оба пункта Оператор может решить на
гейте:

1. В-1 / Е-1: в AC-3 у ветки «отказ записи — сверка до записи не прошла»
   нет названного внешнего триггера (SPEC.md, AC-3; решение №2.1).
   Внешний триггер существует: ответ `GET /user` с `username` из одних
   пробелов (`orchestrator/gitlab_adapter.py:583`, `orchestrator/targets.py:517`,
   `:715-720`). Но SPEC не обязывает реализацию отвечать на него именно
   этой причиной. Стоит назвать триггер в AC-3 или убрать эту ветку из
   долгоживущего теста.
2. Ф-1 (к сведению): решение №1.4 ссылается на `orchestrator/projects.py:996`,
   а `_backup_copy` стоит на `:986`. SPEC ссылается верно.

Отклонения прошлого аудита (spec_sha 0f70a2a1) — В-1 о тексте и коде
выхода, В-2, Д-1, Д-2, Е-1, Е-2 — сняты решениями №2.1–№2.4 и правкой
SPEC.
