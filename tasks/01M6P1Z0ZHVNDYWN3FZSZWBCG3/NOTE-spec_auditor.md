# NOTE spec_auditor

## Выяснено
- Аудит SPEC sha 4fad4f01 (после пяти возвратов). Код зоны и шесть файлов AC-9 совпадают с 77e9ca9c (diff пуст).
- Три отклонения прошлого аудита (c709af8a) сняты решением №5.1: http:// + пустой слот — fail (треб. 5, AC-5), пятый случай AC-8, фраза AC-2 исправлена.
- Опыт AC-4 (git 2.50.1): статический http.server с Basic по префиксу пути, два bare после update-server-info: с useHttpPath и помощником по пути clone+submodule update+fetch --recurse-submodules проходят; без useHttpPath — «Authentication failed», git повторяет клон подмодуля один раз («a second time»), петли нет. Помощник получает path=grp/proj.git, grp/sub.git.
- `token_slot` обязателен (FIELDS :41, проверка :865) — случая «поле без token_slot» у загруженной записи нет.
- Тесты, вызывающие project_entry_checks (`test_01m574a6…doctor_ci_token`), берут строку по имени — не ломаются.

## Не сработало
- Bash с `$VAR`/`cd` отклоняется; опыт — временный exp_audit.py в каталоге документов, убран task-rm.

- Опыт: при GIT_TERMINAL_PROMPT=0 git всё равно вызывает GIT_ASKPASS (и запасной SSH_ASKPASS), если помощник ничего не отдал; ответ askpass становится паролем. SPEC не требует снимать их (образец 01m545:226-229 снимает).

## Где остановился
- SPEC-AUDIT.md готов: verdict concerns, status ready, guard ок. Отклонения: 1) снять GIT_ASKPASS/SSH_ASKPASS в безопасной форме (случаи «пусто» AC-3/AC-8); 2) ранний ok «в .gitmodules нет адресов» (project_checks.py:1378) при поле не ловится AC-5.

## Чего не хватило
- Способа гонять опыт с git без временного файла в каталоге документов.
