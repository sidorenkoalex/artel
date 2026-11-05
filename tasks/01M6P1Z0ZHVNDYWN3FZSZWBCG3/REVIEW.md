---
task: 01M6P1Z0ZHVNDYWN3FZSZWBCG3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Отдельный токен для подмодулей внешнего проекта

## Фаза A: план
- Таблица покрытия полна (требования 1–7 → шаги 1–5); шаги — единицы размера MR.
- Подход (вторая функция `hosting_path_env` и второй помощник вместо правки
  общего) прямо держит AC-2/AC-9: запись без поля идёт прежним
  `hosting_env` без изменений. Перенос разбора `.gitmodules` и
  `_resolve_submodule` в `gitcmd` с делегированием из `doctor` — тела
  перенесены дословно (сверено по diff), имена в `doctor` сохранены.
- «Влияние на систему» = diff: четыре файла кода, плюс карта; `hosting_token`
  и его вызыватели не тронуты; путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py`: `SUBMODULE_TOKENS_FIELD` в `LOCAL_FIELDS["machine"]`, перенос в `_flatten`, `_submodule_tokens_error` (не отображение / пустой путь / пустой слот), отказ при `local=False` с именем поля. |
| 2 | OK | `HOSTING_PATH_CREDENTIAL_HELPER`: хост запроса приводится к нижнему регистру и сравнивается с `ARTEL_HOSTING_HOST` (тоже lower, `url_host` с портом); путь без `/` и `.git` сравнивается точно; совпал с пустым токеном — `exit 0` без пароля, не токен проекта; иначе — токен проекта. `submodule_credentials` берёт `.gitmodules` из `repo_context.clone_path(name)`, разрешает относительный адрес от `url`, пропускает (слот не читает) ssh, не http(s), другой хост/порт (`same_host`). Токены — только в переменных окружения; `eval` раскрывает лишь имя переменной с номером. |
| 3 | OK | Ветка в `gitcmd.git` после `hosting_token` (refusal) — все хостинговые подкоманды, включая `push`; без поля — прежний `hosting_env`, `useHttpPath` не ставится. |
| 4 | OK | `_clone_submodules(clone, entry, target)`: отказ роли → слоты → именованный отказ (путь и слот) до git; места вызова `submodule update` не добавлены. См. наблюдение о `git://` ниже. |
| 5 | OK | Строка заводится при поле и любом `merge_gate` (`elif`); `_field_submodule_problem`: другой хост (с портом) → `fail` с путём и хостом; ssh/scp → `warn`; пустой слот (в т.ч. `http://`) → `fail` со слотом раньше `warn` для `http://`; путь поля вне `.gitmodules`, нет файла, нет адресов → `warn` на каждый путь, ранних `ok` нет. Прочие подмодули — прежняя ветка `_remote_kind`. |
| 6 | OK | В `gitcmd.git` слоты читаются только при `token is not None` (после отказа роли); в `_clone_submodules` `hosting_token` вызывается первым. |
| 7 | OK | Комментарий поля в `targets.py:350-356`. Карту по содержимому не сверял (см. «Проверено исполнением»). |

Наблюдение (не замечание, для Оператора): буквально требования 4/5 говорят
«любой адрес на хосте записи, кроме ssh». Адрес `git://<хост записи>/…` с
пустым слотом код не отказывает в `_clone_submodules` (`submodule_credentials`
пропускает не-http(s)) и в `doctor` даёт `warn` «не http(s)», а не `fail`
(`orchestrator/doctor/project_checks.py` `_field_submodule_problem`). Протокол
`git://` учётных данных не несёт, так что практического сценария поломки нет;
SPEC этот случай явно не разбирает — не дефект разработчика.

## Замечания
Нет blocker/major/minor, требующих правки.

Тесты: разработчик в `tests/` тестов не добавлял и существующие не менял
(diff `tests/` пуст, кроме закреплённого долгоживущего файла задачи) —
ослаблений нет, повторов долгоживущего файла нет. Долгоживущий файл
`tests/test_01m6p1z0zhvndywn3fzszwbcg3_submodule_tokens.py` помечен
«Группа: долгоживущий», у каждого метода есть заявка «Ловит мутацию» с
наблюдаемым расхождением (статус строки, пароль `credential fill`, чтения
связки, argv/окружение).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M6P1Z0ZHVNDYWN3FZSZWBCG3` — 6 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6p1z0zhvndywn3fzszwbcg3_submodule_tokens.py tests/test_hosting_token_units.py tests/test_01m545edths47hsb59akc1ez9c_project_token.py tests/test_doctor_gitlab_ci_file.py tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py tests/test_push_hook_units.py tests/test_push_hook_stand.py` — 190 passed, 108 subtests passed (153 с).
- Сверка `url_host` (`orchestrator/gitcmd.py:84-96`) — читал, чтобы проверить, что scp-адрес `git@<хост>:…` даёт хост записи, а значит `same_host` пропускает его к ветке ssh-`warn`, а не к `fail` «другой хост»: так и есть.
- Не сделано: временную мутацию (`same_host` без порта) не прогнал — запись копии файла вне рабочего каталога отклонена; свежесть `docs/codebase-map.md` не проверял, чтобы не менять рабочую копию генератором.

## Предложения системе
- Приём «временная мутация» из review-checklist требует сохранить оригинал файла; запись в `/tmp` в шаге ревьювера отклоняется — нужен штатный путь (например, `mutation-run` с произвольной правкой) или явное разрешение на временный файл в каталоге документов.
