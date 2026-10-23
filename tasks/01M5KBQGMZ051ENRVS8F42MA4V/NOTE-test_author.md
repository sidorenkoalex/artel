# Записка test_author

## Выяснено
- AC-1..AC-14 — долгоживущий tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py (только cmd_prune + ФС + публичные store/suite_lock); AC-15 — разовый acceptance_tests/test_ac15_retention_docs.py (текст docs/retention.md, модульная строка artel.py: абзац «`prune …» и строка `  prune` после «Модули пакета»).
- Закрытая задача = insert_task(state=done) + store.journal("state -> done") + UPDATE steps SET ts (прецедент tests/test_token_rate_divergence.py:209).
- Замок пишется публичным suite_lock.hand(task_id, run, pid).
- notes-work — RealGitSandbox (настоящий git через self.git("-C", …)); «git не ответил» — испорченный .git/index (rev-parse --show-toplevel при этом отвечает).
- Сбой удаления — подкаталог с chmod 0o500 (откат в addCleanup).
- Число файлов «(<N> файлов)» — рекурсивно, включая .git, без ссылок.
- Стаб prune.py + стаб документации: все тесты зелёные (3 прогона с разными зёрнами), стабы откатаны git checkout. preflight — все проверки пройдены.

## Не сработало
- Составные bash-команды (cd && …, heredoc) требуют подтверждения — стаб писал инструментом Write, откат git -C … checkout.
- В модульной строке artel.py есть и строка usage «  prune [--execute] | …» — искать строку перечня только после «Модули пакета».

## Где остановился
Планка готова, шаг сдан.

## Чего не хватило
Формат lock.json/run.json искал в suite_lock.py::_payload и doctor/orphans.py::_live_suite_run_in.
