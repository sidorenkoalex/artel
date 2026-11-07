# Записка test_author

## Выяснено
- Долгоживущие файлы (коммитит пульт):
  - tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py — AC-1..AC-8 (65 тестов). Подменная программа gh в PATH: правила rules.json (регулярка по argv → JSON / двоичный файл / поток / сон / pidfile), журнал calls.jsonl (argv, GH_REPO, GH_TOKEN, pid). Отвечает на пути раздела критериев SPEC, плюс actions/runs/<id>/jobs; у artifacts соблюдает фильтр name=.
  - tests/test_01m6trm6h57tn8v14hgfv0nqxj_registry_without_report.py — AC-9: дочерний python, хук импорта после exec orchestrator.forge подменяет реализацию хостинга классом без job_test_report. Зелёный с рождения.
- Планка (разовый): acceptance_tests/test_outcome_gate_names.py — только закрытые имена outcome_integrity._ci_report (AC-7) и _CI_PENDING_STATUSES (AC-4); стенд импортирует из долгоживущего файла.
- Пределы config.CI_REPORT_* тесты подменяют monkeypatch.setattr(config, …) — код должен читать config.<имя> при вызове.
- Причины AC-3 сверяются по словам случая (регулярки в setup_case, TIME_WORDS/SIZE_WORDS); случаи компонентов — «компонент» и имя задания вместе.
- Красный прогон: 52 failed / 15 passed (зелены с рождения AC-6 GitLab/литералы, AC-8, AC-5 неверный тип, AC-9). На стабе: 67 + 6 планки зелёные; 12 мутаций стаба ловятся.

## Не сработало
- В Bash отказаны $-подстановки и присваивание окружения перед командой — использовал обёртки на Python.

## Где остановился
- Всё сдано: preflight пройдена, временный стаб удалён task-rm.

## Чего не хватило
- Не нашёл, как plank-run принимает плагин pytest для прогона со стабом — помогла переменная PYTEST_PLUGINS в окружении.
