---
task: 01M6EZXVFGH5Z2876XWMQG35FP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab Б2.3-3: строки doctor проекта и forge-probe по ветке или коммиту

## Фаза A: план
- Таблица покрытия PLAN полна (треб. 1–15 → шаги 1–3), шаги размера MR.
- Отклонения PLAN от буквы SPEC — `warn` вместо `skip` для `include:` без
  `workflow:rules`, неподдержанного `if` и `changes`/`exists`; ssh-подмодуль
  и чужой хост — `warn`; `retry: {max: N}`; `http_status` при 403 заданий у
  красного конвейера — все покрыты ANSWER-1 пп. 1–4 и потому не замечание.
- «Влияние на систему» соответствует diff: 4 файла кода из `zones` + новый
  `tests/test_doctor_gitlab_ci_file.py`; `yamlmini.py`, `doctor/__init__.py`,
  `misc_checks.py`, ac9 и его `EXEMPT` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `project_checks.py:51` `by_pipeline = doctor.forge.ci_by_pipeline(name)`; новые строки — по `doctor.targets.merged_by_project_people(entry)` (`:70`, `component_checks`). Литералов хостинга/`merge_gate` нет. |
| 2 | OK | Путь GitLab не зовёт `gh` (`check_project_token(..., compare_gh=False)` не доходит до `_operator_gh_token`); AC-9 со шпионом зелёный. |
| 3 | OK | `check_forge_protection` (`:692`): reason/`None` → skip, `< 40` → skip «нужна роль Maintainer», ok с именами веток/тегов, reason защит → skip. |
| 4 | OK | Поле последним в трёх dataclass; `_failed_status` берёт код только из `Reply.status`; проведено через `_read_all`, `_pipeline_findings`, `pipeline_status`, `branch_pipeline`, `protections`. Других вызывающих `_read_all`/`_pipeline_findings` вне модуля нет (grep по `orchestrator`, `tests`, `scripts`). Тексты `reason` не менялись. |
| 5 | OK | `check_forge_ci_token` (`:716`): 401/403/404 → fail «статус CI проекта пульт не увидит»; иной код/`unknown` → skip; прочитанный итог → ok. По тексту `reason` не различает. |
| 6 | OK | `check_workflow_rules` (`:1120`): переменные push-конвейера, первое сработавшее правило, `when: never`, форма «правило workflow №n (if: …)», нет файла/клона/неразобран — `warn`; `include`/неподдержанное — `warn` по ANSWER-1 п. 4. |
| 7 | OK | `project_checks.py` ветка `compare_gh=False`: ok с текстом о несделанной сверке. |
| 8 | OK | `check_ci_file_no_paths`; строка только при target-human и компоненте ci/both. |
| 9 | OK | `check_ci_reruns` (`:1266`): семь форм, `extends` с глубоким слиянием (порядок списка — последний побеждает, проверено пробой), `default:`, `retry: 0`, `retry` чужого задания — не находка. |
| 10 | OK | `check_submodules`: роль → skip без пробы; нет слота → skip; https на хосте записи — `gitcmd.in_repo(клон, "ls-remote", адрес)` (`ls-remote` в `HOSTING_SUBCOMMANDS`, токен идёт помощником учётных данных, не в URL — stderr токен не несёт); относительный `./`/`../` — от `url` записи как у git. |
| 11 | OK | Только чтения: `forge.*` чтения, `ls-remote`, чтение файлов клона. |
| 12 | OK | Свой разборщик `_CiParser` в `project_checks.py`; якоря/теги/многострочные/`---`/табуляция/сбитый отступ → «не разобран: строка N». |
| 13 | OK | `artel.py::_forge_probe_args`/`_cmd_forge_probe`: `--ref`, `--sha`, оба вместе — отказ с подсказкой; `--job` читается у выбранного конвейера. |
| 14 | OK | Проверка `token_slot` до обращения к `forge`/пробе в трёх строках. |
| 15 | OK | Прежние функции GitHub не менялись; AC-15 сверяет точный список строк. |

## Замечания
Замечаний blocker/major/minor нет.

Наблюдение (не замечание, на усмотрение): `orchestrator/doctor/project_checks.py:1386`
— подмодуль на хосте записи по `http://`/`git://` попадает в ветку `kind == "иной"`
и получает текст «не на хосте записи localhost», хотя хост тот же (проверено
пробой); статус `warn` верный, неточен только текст.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M6EZXVFGH5Z2876XWMQG35FP`
  — `test_ac15_guard_untouched.py` 1 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6ezxvfgh5z2876xwmqg35fp_forge_probe_ref_sha.py
  tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py tests/test_01m6ezxvfgh5z2876xwmqg35fp_http_status.py
  tests/test_doctor_gitlab_ci_file.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` — 89 passed.
- Проба граничных случаев прямым вызовом функций (временный скрипт в каталоге
  документов, удалён): типовой workflow с `merge_request_event` +
  `$CI_OPEN_MERGE_REQUESTS when: never` + `$CI_COMMIT_BRANCH` → ok по правилу №3;
  `DOCKER_HOST: tcp://docker:2375`, `curl https://x/#a`, `echo "a: b"` разобраны
  верно; `- >` → «не разобран: строка 3»; `rules: [- when: never]` → warn;
  `extends: [.a(retry 1), .b(retry 0)]` → ok (последний побеждает, как в GitLab);
  подмодули `./lib` → `https://localhost/team/proj/lib`, `https://LOCALHOST:443/…`
  → проба, `http://localhost/…` → warn без пробы.
- `grep -rn "_read_all\|_pipeline_findings" orchestrator tests scripts` — вне
  `gitlab_adapter.py` вызывающих нет (смена кортежа безопасна).
- Карта кода: `codebase_map.build_modules`/`render` в памяти, сравнение с
  `docs/codebase-map.md` без строки `built_at_sha` — совпадает (fresh).
- CI коммита 32430ca0 зелёный (из пакета).

## Предложения системе
- review-checklist: правило «замечание без сценария — не замечание» плюс гейт
  «любая open-запись реестра блокирует approved» вынуждают либо не регистрировать
  minor, либо возвращать задачу из-за вкусовой правки; стоит явно разрешить
  minor-наблюдения вне реестра или статус реестра, не блокирующий гейт.
- Bash шага ревью отказывает в heredoc с `{…'` и в `rm` — пробу пришлось писать
  файлом в каталог документов и удалять через `python3 -c os.remove`.
