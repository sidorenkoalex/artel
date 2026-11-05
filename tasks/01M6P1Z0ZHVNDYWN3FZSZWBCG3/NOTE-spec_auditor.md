# NOTE spec_auditor

## Выяснено
- Аудит SPEC sha 88de96c3 (после двух возвратов, решения №1.1–6, №2.1–6). HEAD fbe2aebec: файлы зоны совпадают с 77e9ca9c и origin/main.
- Факты о коде подтверждены: gitcmd.py:42, :51-56, :61-78, :122-210, :1286-1296; workspace.py:141-153, :190-196; project_checks.py:70-75, :1308-1400; targets.py:41, :366, :796-810, :837-916 (`local` флаг check — прецедент `verify`, годится для «только локальный слой»).
- Опыт (git 2.50.1 Apple): GIT_CONFIG_NOSYSTEM=1 убирает osxkeychain (/Library/.../git-core/gitconfig); useHttpPath: url …/g/p → path=g/p, …/p.git/ → path=g/p.git; credential fill без ответа помощника и без GIT_TERMINAL_PROMPT=0 идёт к /dev/tty (без tty — «Device not configured», с tty — ждёт ввода).
- Хост: помощник — url_host (netloc с портом), doctor — _remote_kind (hostname без порта, нижний регистр) — разные понятия «другого хоста».
- Тесты, закрепляющие меняемое вне AC-9: tests/test_push_hook_units.py:199-211 (hosting_env с 3 арг., fill), tests/test_push_hook_stand.py:606-611 (carries_token), test_target_set.py:270-272 (LOCAL_FIELDS динамически — не ломается).

## Не сработало
- Bash с `$VAR`/`;`-цепочками отклоняется; опыт — временный exp_audit.py в каталоге документов, убрать task-rm.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок; exp_audit.py убран task-rm. 7 отклонений: AC-7 не ловит токен в GIT_CONFIG_VALUE помощника; нет GIT_TERMINAL_PROMPT=0/timeout у прямого credential fill (AC-3/5/8); хост url_host vs _remote_kind; клон без .gitmodules при поле → ранний ok; литерал GIT_CONFIG_* задевает GIT_CONFIG_GLOBAL; не названы test_push_hook_units/stand; текст warn http:// «не на хосте записи».

## Чего не хватило
- Способа гонять опыт с git без временного файла в каталоге документов.
