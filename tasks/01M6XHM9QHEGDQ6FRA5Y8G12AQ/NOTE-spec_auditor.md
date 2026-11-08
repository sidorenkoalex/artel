# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: status ready, verdict concerns, spec_sha 019d68cd…; guard ок.
- Опытом: pytest меняет PYTEST_CURRENT_TEST между setup и teardown — отпечаток «окружения» целиком краснит каждый тест.
- Опытом: в PATH роли нет /bin — `ps` по имени FileNotFoundError; пульт зовёт /bin/ps (acceptance.py:1675, doctor/stale_cycles.py:49).
- Опытом: после copytree первый `git status` переписывает .git/index, последующие — нет (мутация «индекс побайтно» ловится, только если индекс устарел к первому тесту).
- Опытом: одно имя фикстуры (уровня функции) + Module.addfinalizer даёт песочницу на модуль со сторожем на тест; scope="module" сторожить на каждый тест не может.
- RealGitSandbox: всегда создаёт БД (sandbox.py:1978); симлинк .artel/projects/artel/repo -> root (sandbox.py:1542); origin под mkdtemp вне root (sandbox.py:2009, :2050).
- TmpRootTest подменяет subprocess.run на SpyRun (sandbox.py:1705-1708) — отпечатку нужен _REAL_RUN.
- Существующие тесты по коду не краснеют.

## Не сработало
- heredoc/printf в Bash отклоняются — опыты делал одним `python3 -c` с tempfile.mkdtemp.

## Где остановился
- Готово.

## Чего не хватило
- Знания, что PATH роли без /bin: нашёл только упав на `ps`.
