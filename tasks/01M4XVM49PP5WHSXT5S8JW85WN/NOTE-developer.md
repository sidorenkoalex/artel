## Выяснено
ANSWER-2 ограничил шаг одной capability-пробой, без правок кода/SPEC/тестов/песочницы. Проба выполнена 14.10.2026: AF_UNIX connect к /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/cap-probe-14.sock получил PermissionError errno 1, [Errno 1] Operation not permitted. Kernel peer PID 15302 проверить не удалось: getsockopt не достигнут; данных и ответа broker нет.
Клиент Python через stdin во вложенном zsh: pid=49302, ppid=42800, pgid=sid=49302. БД mode=ro: in_dev, lease.pid=39607, lease.pgid=42800. Промежуточного shell измерение не показывает; многоуровневая ancestry и start-time не проверены. Linux/Claude не проверены.
## Не сработало
IPC отказан на connect. Повторных попыток, обходов, изменения прав, endpoint и fallback на ENV/PGID не было. Exit 0 инструмента — обработанное диагностическое исключение, не успех IPC.
## Где остановился
PLAN status: escalate, новый батч о продолжении исследования после EPERM вместо прежнего вопроса выбора A/B/C. Код и тесты не менялись; полный набор и планка не запускались. Прежнее воспроизведение AC-1 сохранено в PLAN. Нужны решение Оператора о канале, согласование нового SPEC и UNKNOWN. scripts/guard.py PLAN.md: GUARD ок (1 файлов), exit 0.
## Чего не хватило
Разрешённого IPC-канала в настоящей песочнице; writable suite-run не гарантирует AF_UNIX connect. Нет штатной команды пульта для такой диагностики — предложение записано в PLAN.
