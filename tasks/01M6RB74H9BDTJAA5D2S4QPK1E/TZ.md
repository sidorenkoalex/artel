---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new, сверка перед отправкой

# Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new, сверка перед отправкой

## Факты

1. Поле `machine.commit_author` записи локального слоя — автор коммитов пульта и ролей проекта: форма `{name, email}` (`orchestrator/targets.py:715-720`), чтение — `gitcmd.commit_author` / `pult_identity` / `pult_identity_args` (`orchestrator/gitcmd.py:567-582`); у коммитов ролей оно перекрывает идентичность окружения роли (`orchestrator/runner.py:1354-1356`). Поле необязательно: без него коммиты пульта подписаны автором по умолчанию (`fixation.FIXATION_AUTHOR_EMAIL`, `orchestrator/artifact_branch.py:316`).
2. Опыт 06.11 (строки копилки 06.11): GitLab с серверным хуком `pre-receive` отклоняет push, если email каждого нового коммита не равен адресу учётной записи отправителя; для бота токена проекта адрес — `commit_email` пользователя токена (вид `project_<id>_bot_<хэш>@noreply.<хост>`), имя автора сервер не проверяет. Первая задача внешнего проекта набрала пять коммитов с автором по умолчанию до первой отправки; отправка их всех была отклонена, задачу пришлось закрыть обходом.
3. Адаптер GitLab уже разрешает `GET /user` (`orchestrator/gitlab_adapter.py:63`) и читает из ответа только `username` (`token_user`, `:577-584`; `forge.TokenUser`, `orchestrator/forge.py:96-98`); вызовы — `orchestrator/artel.py:2464`, `orchestrator/gitcmd.py:636`.
4. Проверки проекта `doctor` — `orchestrator/doctor/project_checks.py` (образец — `check_project_token`, `:254`); `doctor --fix` уже правит локальный слой (клон проекта, файл политики). Запись поля слоя с копией прежнего файла и журналом — путь `target-set` (`orchestrator/projects.py`: `_target_set_load`, `_rendered`, `_target_set_write`).
5. `new` — `catalog.cmd_new` (`orchestrator/catalog.py:775`); первый коммит артефактной ветки и его отправка происходят внутри `new`.
6. Все отправки пульта в проекты под белым списком проходят `gitcmd._push_plan` (`orchestrator/gitcmd.py:1264`; отказ белого списка — `_whitelist_refusal`, `:975`; политика клона — `_push_policy_refusal`, `:482`, вызов `:1346`).

## Требуется

1. **Адрес учётной записи токена.** `forge.TokenUser` несёт, кроме `username`, `name` и `commit_email`; адаптер GitLab берёт `commit_email`, при его отсутствии — `email` ответа `GET /user`. Прочие адаптеры поля не заполняют.
2. **Автопоиск в `doctor --fix`.** Для проекта с `forge: gitlab` и `token_slot`, у записи которого нет `machine.commit_author`: `doctor --fix` записывает `machine.commit_author` = `{name: <name пользователя токена>, email: <commit_email>}` в локальный слой путём `target-set` (копия прежнего файла, сверка до записи, строка журнала). Ответ API без адреса или отказ API — запись не делается, строка `doctor` называет причину. Уже заданный `commit_author` автопоиск не перезаписывает.
3. **Сторож в `doctor`.** Новая проверка `project-commit-author-<проект>` для проекта с `forge: gitlab` и `token_slot`: `ok` — `commit_author.email` равен адресу учётной записи токена; `fail` — поле не задано («автор коммитов не задан: doctor --fix») или адрес другой («токен сменился или автор задан неверно: <записано> против <адрес токена>; doctor --fix не перезаписывает — правка target-set»); `warn` — API не ответил или не дал адреса. Значения токена в вывод не идут.
4. **Отказ `new`.** `new --target <проект>` для проекта, у которого проверка требования 3 даёт `fail`, отказывает до создания задачи и артефактной ветки, текстом проверки; `warn` (API не ответил) — задача заводится с предупреждением в выводе.
5. **Сверка перед отправкой.** В `_push_plan` для проекта под белым списком с заданным `commit_author`: каждый отправляемый коммит, которого нет в origin (не достижим из текущего значения назначения в origin и из ссылок слежения `refs/remotes/origin/*`), обязан иметь email автора и коммитера, равный `commit_author.email`; иначе — отказ отправки до git с перечнем sha (не больше 10, затем «и ещё N») и их адресов. Удаление (`--delete`, `:<ветка>`) сверку не проходит.
6. Проекты без `commit_author` и проект артели — поведение отправки прежнее; прежние отказы белого списка, их порядок и тексты — без изменений; новая сверка идёт после них.

## Критерии приёмки

- Given вымышленная запись GitLab без `commit_author` и подменённый ответ `GET /user` с `name`, `commit_email`, When `doctor --fix`, Then в разобранном слое `machine.commit_author` = `{name, email: commit_email}`, создана копия прежнего файла, строка журнала; повтор — без изменений;
- Given ответ без `commit_email`, но с `email`, Then записан `email`; ответ без обоих или отказ API — слой побайтно прежний, строка `doctor` с причиной;
- Given `commit_author` задан и равен адресу токена, Then проверка `ok`; другой адрес — `fail` с обоими адресами, `doctor --fix` поле не меняет; поля нет — `fail` с подсказкой `doctor --fix`; API не ответил — `warn`;
- Given проверка `fail`, When `new --target <проект>`, Then отказ текстом проверки, задачи и артефактной ветки нет; `warn` — задача заведена, предупреждение в выводе;
- Given клон с двумя недосланными коммитами, один из которых с чужим адресом автора, When отправка через `_push_plan`, Then отказ до git с sha и адресом чужого коммита; все с адресом `commit_author` — отправка идёт; коммиты, уже достижимые из origin, сверку не проходят; `--delete` — без сверки;
- проект без `commit_author` и проект артели — отправка как прежде; существующие тесты — зелёные без правки.

Безопасность тестов: вымышленные проекты и адреса, локальный слой и клоны — во временной песочнице (`tests.sandbox`); ответ API — подмена `gitlab_adapter.request`/транспорта, без сети; отправка — в локальный голый репозиторий-дублёр origin; никогда — настоящий `.artel/targets.yaml` и связка ключей.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/forge.py` (`TokenUser`), `orchestrator/gitlab_adapter.py` (`token_user`), `orchestrator/doctor/project_checks.py` (новая проверка и её `--fix`), `orchestrator/doctor/cli.py` (регистрация проверки, если нужна), `orchestrator/projects.py` (функция записи поля для `doctor --fix` путём `target-set`), `orchestrator/catalog.py` (`cmd_new`: отказ), `orchestrator/gitcmd.py` (`_push_plan`: сверка), `docs/codebase-map.md` (только генерацией), `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/targets.py`, `orchestrator/runner.py`, `orchestrator/artifact_branch.py`, `orchestrator/github_adapter.py`, `orchestrator/artel.py`, `tests/sandbox.py`, `docs/target-onboarding.md`.

Не входит:
- автопоиск и сторож для GitHub и других хостингов;
- переподпись уже сделанных коммитов;
- исключение для коммитов после rebase/cherry-pick (AuthorDate ≠ CommitDate);
- правка `docs/target-onboarding.md` (документ — правкой Оператора отдельно).
- правка настоящего локального слоя `.artel/targets.yaml` в тестах и при разработке.

Приоритет 2.

Рамка: $45. Набор моделей — по умолчанию.
