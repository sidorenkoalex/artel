---
task: 01M6RB74H9BDTJAA5D2S4QPK1E
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Автор коммитов пульта для проекта на GitLab: автопоиск, сторож, отказ new

## Фаза A: план
- Таблица покрытия полна: требования 1–5 — шаги 1–4, требования 6 и 7 закрыты
  тем, что существующие тесты и `gitcmd.py` не тронуты (diff это подтверждает:
  `tests/` — только три новых файла, `orchestrator/gitcmd.py` в diff нет).
- Шаги размером с MR, подход не спорит с архитектурой: запись идёт через
  рубежи `target-set` (`_local_layer_for` вынесен из `_target_set_load`, тексты
  отказов прежние, к ним только дописывается префикс `target-set: `), сверка —
  уже существующая `_target_set_block_mismatches`.
- «Влияние на систему» совпадает с diff: 6 файлов кода в зонах SPEC, плюс новый
  тест и карта.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `forge.py:99-102` — поля `name`/`commit_email` со значением `None` по умолчанию; `gitlab_adapter.py:586-591` — `commit_email`, иначе `email` (пустой или пробельный адрес считается отсутствующим). GitHub новые поля не заполняет. |
| 2 | OK | `project_checks.fix_commit_authors`: условие «поля нет», в процессе роли выходит до `token_user`, причины выводятся строкой с именем проекта; `{name: username, email: commit_email}`. |
| 3 | OK | `projects.set_commit_author` (`projects.py:494-535`): возвращает причину, `sys.exit` не зовёт; копия через `_backup_copy`, сверка `_target_set_block_mismatches` по `machine.commit_author` целиком (с `_merge_mismatches` → `merge_local`), строка журнала `target-set` от `doctor`. Отказ сверки — «сверка до записи не прошла». |
| 4 | OK | `check_commit_author`: skip в роли / warn при отказе API или без адреса / fail «автор коммитов не задан: doctor --fix» / fail при несовпадении, текст называет оба значения и фразу о правке Оператором / ok. GitLab определяется через `ci_by_pipeline`, без литерала. Токен в текст не попадает: в тексте только `username`, адреса и `reason` адаптера. |
| 5 | OK | `catalog._commit_author_gate` вызывается в `cmd_new` сразу после `unsupported_reason` (`catalog.py:877`), до `_new_refs`, клона, id и ссылки документов; путь `epic draft promote` проходит через `cmd_new`. |
| 6 | OK | Существующие тесты не тронуты, мандатом ANSWER-1/2 не пользовались; `pair_support` и `unsupported_project` зелёные. |
| 7 | OK | `orchestrator/gitcmd.py` не изменён. |

## Замечания
Blocker и major нет. Наблюдения, которые вердикт не меняют:
- minor — `orchestrator/doctor/cli.py:340` — заголовок «Автор коммитов проектов
  по владельцу токена:» выводится в каждом `doctor --fix`, даже без проектов
  GitLab и в процессе роли (там `fix_commit_authors` сразу возвращается). Это
  косметика: пустой заголовок ничего не ломает. В реестр не заношу, потому что
  последствий у этого нет.
- Тест `tests/test_commit_author_units.py` не повторяет долгоживущие файлы
  задачи: в них нет сценариев «хостинг без конвейеров» и «отказ
  записи артели / записи вне слоя / слоя с комментарием». У каждого метода есть
  заявка «Ловит мутацию», и при мутации наблюдаемо меняется результат
  (`AttributeError` у `None` из подменённого `token_user`, срабатывает
  `AssertionError` подменённого `sys.exit`, файл меняется побайтно).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_commit_author_units.py tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_commit_author.py tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_token_user.py` — 33 passed (53.6 с).
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` — 28 passed (требование 6: файлы мандата зелёные без правки).
- `artel.py plank-run 01M6RB74H9BDTJAA5D2S4QPK1E` — отказ «планки нет: … нет файлов test_*.py; pytest не запускался». Все критерии задачи закрыты долгоживущими файлами `tests/`, их прогон указан выше.
- `git diff --stat 6bde2b9e6...HEAD -- tests/` — только 3 новых файла (+901), существующие тесты не изменены.
- `grep` по `docs/codebase-map.md` — новые символы (`set_commit_author`, `_local_layer_for`, `fix_commit_authors`, `_commit_author_gate`, `test_commit_author_units`) в карте есть.
- Временную мутацию (сверка имени с `name` вместо `username`) запустить не удалось: команду правки и отката отклонил режим разрешений. Сторожа этой мутации — случаи «имя — name» и «ok» в `test_ac4_guard_status_by_case`; их заявка сверена с кодом при чтении.

## Предложения системе
- Миссия ревью разрешает приём «временная мутация», но в шаге ревьювера составная команда «правка → прогон → откат» требует подтверждения, которого никто не даст (`.artel/home/.claude/settings.json`). Нужна разрешённая команда пульта для временной мутации (по образцу `plank-run`).
