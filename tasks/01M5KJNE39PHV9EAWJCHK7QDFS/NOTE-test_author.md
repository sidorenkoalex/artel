# Записка test_author — 01M5KJNE39PHV9EAWJCHK7QDFS

## Выяснено
- tests/__init__.py на базе пуст.
- Долгоживущий файл: tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py — AC-1…AC-8. Модульные случаи подменяют `shutil.which` (и `direct_git.which`, если импортирован из shutil) и `subprocess.run` глобально; подмена which ищет git по переданному `path=`, без `path=` не находит ничего.
- AC-6 (проводка): подпроцесс `python -c`, в sys.modules заранее поддельный `tests.direct_git`, затем `import tests`; ожидается один вызов с самим `os.environ`.
- AC-8 — на TmpRootTest: она подменяет `subprocess.run` глобально (SpyRun), поэтому git по абсолютному пути вызывается через Popen.
- Разовая планка: acceptance_tests/test_oneoff_init_and_plan.py — AC-6 (в tests/__init__.py нет другой правки: дифф без удалённых строк + разбор AST) и AC-9 (PLAN.md через artifact_text, текстовые признаки замеров).
- Импорт `tests.direct_git` на уровне модуля ронял сухой сбор перехода — перенесён внутрь тестов.
- Проверено стабом реализации: всё зелёное; мутации (снята платформа, exists без X_OK, без normpath, which без path, без проверки rc, timeout≠5, `DIRECT_GIT_DIR=None` без вызова) дают красный. Стаб удалён.

## Не сработало
- `cat`/`ls`/`rm` в Bash нет; при упавшем `rm` в цепочке `git reset HEAD~1` после `;` сдвинул ветку — вернул на 62012f08. Откат временного коммита — только на явный sha.

## Где остановился
- Готово: preflight пройдена, планка: 1 passed (AC-6 на стабе) / AC-9 красен до PLAN.md.

## Чего не хватило
- Что сухой сбор отклоняет ошибку импорта долгоживущего файла (acceptance.collect, код ≠0) — узнал из кода.
