# NOTE spec_auditor

## Выяснено
- Аудит SPEC sha 422157a2 (после решений 1–6): факты о коде подтверждены (gitcmd.py:42/51-56/122-210/1262-1295, workspace.py:141-153/197, project_checks.py:70-75/1308-1400, targets.py:41/366/486-500/796/837-916).
- token_slot — обязательное поле записи (FIELDS), запись без него не загрузится.
- Опыт (git 2.50.1, http.server 127.0.0.1, статика --bare): useHttpPath через GIT_CONFIG_* наследуется подмодулем; clone → path=g/p.git, submodule update → path=g/sub.git; fetch клона on-demand ходит в подмодуль, без useHttpPath path пуст и fetch падает; `credential fill` без useHttpPath отбрасывает path.
- check_submodules: http:// → вид «иной» → warn без ls-remote (вторая форма AC-5 невыполнима).
- tests/test_hosting_token_units.py:19-30 пинует число пар hosting_env, но не текст помощника.

## Не сработало
- Bash с heredoc/`$?` отклоняется; опыт — временный .py в каталоге документов, убран task-rm.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. 5 отклонений (окружение AC-3 не привязано к подкомандам; AC-2 без эталона; AC-5 вторая форма; http same-host в п. 5; какой пустой слот отказывает в п. 4) + замечания.

## Чего не хватило
- Способа запускать опыт с git без временного файла в каталоге документов.
