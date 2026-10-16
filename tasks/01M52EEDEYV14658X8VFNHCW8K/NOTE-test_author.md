# Записка test_author — 01M52EEDEYV14658X8VFNHCW8K

## Выяснено
- Все AC — свойства кода → два долгоживущих файла в tests/: `..._profile_runner.py` (AC-1..6, 8) и `..._launch_places.py` (AC-7).
- Долгоживущий файл не может трогать `acceptance._run_full_suite_now`/`_to_log`/`two_sided._run_side` напрямую (guard: закрытый атрибут). Пути к ним публичные: `acceptance.run_full_suite` (log=None → _now без observe; внутри `acceptance.observed_full_suite()` → _now с observe, Popen; log=путь → _to_log), `two_sided.run(repo, branch, base_sha, [Method])` → `_run_side` (нужен настоящий git — RealGitSandbox).
- Подмена: `mock.patch.object(acceptance, "subprocess", ns)` / `(two_sided, "subprocess", ns)` — модульная, не задевает git в gitcmd/stack. `tempfile.mkdtemp` подменён детерминированным (каталог `<prefix>N`), чтобы путь junit и scratch two_sided были литералами (замечание О2 аудита).
- observe-путь зовёт `/bin/ps` через тот же subprocess.run — фейк отвечает строкой процесса, иначе ctypes-фолбэк со sleep.

## Не сработало
- `cat`/`;` в Bash недоступны.

## Где остановился
- Готово: оба файла в tests/, предпроверка пройдена по всем пунктам. Каталог acceptance_tests/ пуст — `plank-run` отвечает «планки нет», это ожидаемо.
- launch_places: 8 зелёных тестов на текущем коде; мутация «лишняя переменная в `_pytest_env`» роняет 21 подтест.
- profile_runner: красен до реализации («неизвестное подполе runner»). Под временным стабом (targets.py: виды runner/mapping, workdir как dir, условие pytest-own; Profile: поля со значениями по умолчанию + from_values) зелены все тесты вместе с test_01m45…_test_profile.py, test_project_profile_gates.py, test_network_address_gate.py. Стаб откатан через git checkout. Мутации «сверка без учёта регистра» и «перечень литералом» ловятся.
- docs/codebase-map.md не регенерировал: правку вне tests/ пульт откатил бы. Регенерирует разработчик.

## Чего не хватило
- —
