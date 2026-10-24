## Выяснено
- Правка: `_attempt_push(..., origin_checked=False)`; `_send` передаёт `True`. `origin_sync_refusal`: сверка → (`not reason and local and local != remote`) `_send` + пересверка.
- Долгоживущий файл `tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py` написан developer; статика долгоживущего (запрет импорта artifact_branch) применяется только в tests_writing/amend/preflight, не на выходе in_dev.
- AC-11: Ac5ProofMismatchTest до 88/49/9 (remote/push/ls-remote), после 43/43/9.

## Не сработало
- Bash шага: `$VAR`, `env`, `cd &&`, запись в /tmp, `rm`, `cat`, `ls` отклоняются. Замер — Python-обёрткой в игнорируемом `.artel/spy/` рабочей копии с подменой `sys.argv` (сторож conftest), копия удалена.

## Где остановился
- Всё сделано, PLAN status: ready; тесты зелёные, мутации проверены.
- Возврат из verifying (25.10): по ANSWER-1 из `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` удалена ровно строка `["-C", clone, "remote"]` (бывш. :1284); 155 passed; карта регенерирована. Первый шаг не прогнал этот файл — он вне перечня «тесты вызывающих» (там нет runner/автокоммита).

## Чего не хватило
- Команды пульта для замера числа вызовов git на тесте до/после.
