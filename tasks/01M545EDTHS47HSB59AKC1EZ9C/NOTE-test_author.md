# Записка test_author

## Выяснено
- Планка: долгоживущий `tests/test_01m545edths47hsb59akc1ez9c_project_token.py` (AC-1…AC-10, AC-12…AC-16) и разовый `acceptance_tests/test_ac11_push_closing_sha.py` (AC-11 зовёт закрытую `_push_closing_sha` — в долгоживущем файле нельзя; импортирует `ProjectSandbox` из долгоживущего файла).
- Валидация стабом проведена: временный стаб (gitcmd.git + GIT_CONFIG_COUNT/KEY/VALUE с пустым credential.helper, GH_TOKEN в ci.gh и check_base_branch, проверки п.5 в doctor/cli.all_checks, подмена keychain.token в TmpRootTest/RealGitSandbox.setUp) — 18 passed + AC-11 passed; три мутации стаба ловятся. Стаб откачен `git checkout`.
- `targets.check` (orchestrator/targets.py:158) требует `token_slot`; запись «без token_slot» в тестах — подмена публичной `targets.load`.
- yamlmini не разбирает кавычки в потоковом списке: `no_paths: [a, **/conftest.py]` без кавычек.
- `git credential fill` с `url=file://…` вызывает помощников, включая `credential.<file-URL>.helper`.
- ОСТОРОЖНО: системный gitconfig машины несёт `osxkeychain`; `credential fill` по https-адресу достаёт настоящий токен. В тестах — только file://-адреса и `GIT_CONFIG_NOSYSTEM=1`.
- Строки проверок doctor ищутся по тексту AC или сравнением двух состояний по `Check.name` (ok→fail).
- Долгоживущий файл не может импортировать `gitcmd` (признак «git-модуль») — git пульта зовётся через `repo_context.git(RepoContext(...))`.

## Не сработало
- `ls`/`cat` в Bash нет; heredoc с `{` и кавычками Bash отклоняет — правки через Edit.

## Где остановился
- Шаг закончен: после отката стаба планка красна по объяснённой причине (45 failed / 10 passed в долгоживущем; AC-1 и хостинговая часть AC-15 зелёные с рождения — поведение main), `preflight` — все проверки пройдены.
- Карту `docs/codebase-map.md` не регенерировал: правка вне tests/ у test_author откатывается — регенерация за разработчиком.

## Чего не хватило
- Имён новых проверок doctor в SPEC — пришлось искать строки сравнением состояний.
