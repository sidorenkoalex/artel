# Записка test_author — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Планка (acceptance_tests/) пуста: все AC — долгоживущие, три файла в tests/:
  - test_01m6zemzb8q1pkrxmjbjstpr7t_template_rules.py — малый, AC-1..AC-8 (поверхности решения);
  - test_01m6zemzb8q1pkrxmjbjstpr7t_template_runs.py — средний, AC-9..AC-14 (настоящие прогоны);
  - test_01m6zemzb8q1pkrxmjbjstpr7t_sandbox_place.py — большой, AC-15 (дочерние pytest).
- preflight: все проверки «пройдена». plank-run отказывает «планки нет» — ожидаемо, файлы tests/ гонялись pytest напрямую.
- Красная фаза: везде AttributeError на отсутствующих config.PYCACHE_TEMPLATES_* / acceptance.<функциях>.
- Стаб реализации (acceptance.py, config.py, sandbox.py) — все 90 тестов зелёные; мутации стаба ловятся
  (без фильтра AC-2, префикс-ссылка, без staging, PYTHONDONTWRITEBYTECODE у сборки, место 0755,
  окружение пульта у запроса pytest-own, cwd прогона у запроса, распознавание обёртки, двойная строка,
  нет .failed, снята проверка доверия, наполнение без run_dir, sandbox ставит только константу / ничего).
  Стаб откатан git checkout, временные файлы убраны task-rm.
- Не ловится в среднем файле: «из исключений убран только cwd» — cwd песочницы вне путей интерпретатора.
- Признаки, которых ждут тесты (из указания Оператора п.2 и SPEC): вызов pytest прогона — элемент "pytest" в argv;
  запрос — без "pytest" и без PYTHONPYCACHEPREFIX в env; сборка — без "pytest", с PYTHONPYCACHEPREFIX;
  AC-12 (д) подменяет subprocess.run только у вызова сборки. Тест убирает PYTHONPYCACHEPREFIX из os.environ.
- Наблюдение «в момент вызова» — подкласс subprocess.Popen (через него идёт и subprocess.run).
- Строка о сбое ловится capsys (print в sys.stderr).
- Время: средний файл ~66 с (сборка шаблона на тест — фикстуры module запрещены без shared_readonly),
  AC-15 ~27 с (дочерние pytest — 4 параллельных процесса по node id; xdist внутри шага роли режет сторож conftest).

## Не сработало
- Длинный heredoc в Bash — «Parser aborted»; скрипты — файлами в каталоге документов.
- Фикстуры scope="module" — отказ preflight (ADR-0032 п.4, только shared_readonly).
- xdist в дочернем pytest AC-15 — сторож роли conftest.py роняет рабочие процессы (нет аргументов-путей).
- Абсолютные пути в argv дочернего pytest — сторож роли требует форму tests/<файл>.

## Где остановился
- Готово к сдаче шага.

## Чего не хватило
- Правило «фикстура module только через shared_readonly» не названо в скиле test-authoring — нашлось только preflight.
