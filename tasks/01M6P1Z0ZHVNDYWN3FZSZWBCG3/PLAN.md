---
task: 01M6P1Z0ZHVNDYWN3FZSZWBCG3
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Отдельный токен для подмодулей внешнего проекта

## Подход
Запись без `submodule_tokens` не меняется ни байтом: `hosting_env` и
`HOSTING_CREDENTIAL_HELPER` остаются как есть (AC-2, AC-9). Для записи с
полем `gitcmd.git` собирает окружение второй функцией
`hosting_path_env`: тот же сброс чужих помощников, другой помощник
`HOSTING_PATH_CREDENTIAL_HELPER` и пара `credential.useHttpPath=true`.
Новый помощник сравнивает хост без учёта регистра (хост записи — `url_host`
с портом, в нижнем регистре), снимает с пути запроса `/` и `.git` и ищет
его среди `ARTEL_HOSTING_SUB_PATH_n`; совпал — отдаёт
`ARTEL_HOSTING_SUB_TOKEN_n` (пустой — ничего, не токен проекта), не
совпал — токен проекта. Токены — только в переменных окружения, не в
тексте помощника и не в argv.

Список подмодулей с токенами строит `gitcmd.submodule_credentials(name,
entry)`: `.gitmodules` клона `repo_context.clone_path(name)` (не каталога
вызова), относительный адрес — от `url` записи; подходят только пути поля,
что есть в `.gitmodules`, с адресом `http(s)://` на хосте записи. Остальные
(ssh, другой хост/порт, нет в `.gitmodules`) слот не читают. Разбор
`.gitmodules` и разрешение относительного адреса переезжают в `gitcmd`
(`gitmodules_entries`, `resolve_submodule_url`); `doctor`
(`gitmodules`, `_resolve_submodule`) делегирует им — одно правило на
помощник и `doctor`, без зависимости `gitcmd` от `doctor`.

`hosting_token` не меняется; слоты подмодулей читаются только после него
(в процессе роли — его прежний отказ, связка не читается).
`_clone_submodules` получает имя проекта: сначала `hosting_token` (отказ
роли), затем `submodule_credentials` — пустой слот подходящего подмодуля —
именованный отказ с путём и слотом до git.

`doctor`: строка `project-submodules-<проект>` и для записи с полем при
любом `merge_gate`; подмодуль из поля — по правилам требования 5 (другой
хост по `url_host` → `fail`, ssh → `warn`, `http://` → `warn`/`fail` при
пустом слоте, пустой слот → `fail` со слотом, `https://` → проба
`ls-remote`, которая сама идёт с токеном слота через `gitcmd.git`); путь
поля вне `.gitmodules` (и при отсутствии файла/адресов) → `warn`. Прочие
подмодули — прежняя ветка.

`targets`: поле `submodule_tokens` в `LOCAL_FIELDS["machine"]`, перенос в
`_flatten`, проверка формы в `check` (отображение непустых строк); в записи
слоя репозитория (`local=False`) — отказ, как у `verify`.

## Шаги
1. `orchestrator/targets.py`: поле, комментарий, `_flatten`, проверка в `check`.
2. `orchestrator/gitcmd.py`: `gitmodules_entries`, `resolve_submodule_url`,
   `submodule_credentials`, `HOSTING_PATH_CREDENTIAL_HELPER`,
   `hosting_path_env`, ветка в `git`.
3. `orchestrator/workspace.py`: `_clone_submodules(clone, entry, target)` —
   порядок «отказ роли → слоты → git».
4. `orchestrator/doctor/project_checks.py`: условие строки и ветка
   подмодулей поля в `check_submodules`; делегирование разбора в `gitcmd`.
5. `python3 scripts/codebase_map.py`; прогон долгоживущего файла задачи и
   файлов AC-9; `plank-run`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 3 |
| 5 | 4 |
| 6 | 2, 3 |
| 7 | 1, 5 |

## Влияние на систему
Запись без поля: окружение, argv и текст помощника прежние (эталон AC-2,
файлы AC-9 не трогаются). `hosting_token` и его вызыватели не меняются.
`doctor` для записей без поля: прежнее условие строки и прежние тексты;
`gitmodules`/`_resolve_submodule` сохраняют имена и поведение (тело
переехало в `gitcmd` дословно). Гейты, лимиты, тесты не ослабляются. Откат
— revert merge-коммита; после отката запись локального слоя с полем
`submodule_tokens` отвергается «неизвестное поле» — поле надо убрать из
локального слоя вместе с откатом.

Проверено в шаге: долгоживущий файл задачи — 61 passed; шесть файлов AC-9
— 129 passed; `plank-run` — 6 passed; соседние тесты targets/workspace/
doctor — 183 passed, 1 failed:
`tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py::EnsureCloneSurvivesFetchFailureTest::test_ac3_fetch_failure_keeps_clone_and_prints_reason`
— таймаут 120 с; тот же таймаут на коде базы (`git checkout HEAD~1 --
orchestrator/`), тест про артель, куда правка не заходит — среда машины,
не дефект задачи.

## Риски
- Помощник — sh-код с `eval` по номеру; значения путей и токенов не
  проходят через `eval` (только имя переменной с числом).
- `tr` в помощнике — внешняя команда; есть в любом POSIX-окружении.

## Предложения системе
- Нет штатного способа прогнать один тест на коде базы, чтобы отличить
  среду от регрессии: пришлось `git checkout HEAD~1 -- orchestrator/` и
  возврат руками (класс «обход вместо команды пульта»; `mutation-run
  --ref base` близко, но про мутации).
