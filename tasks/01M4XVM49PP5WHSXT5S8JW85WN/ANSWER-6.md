---
task: 01M4XVM49PP5WHSXT5S8JW85WN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-6: ответ Оператора

## Ответы

Оператор 15.10.2026 разрешил настроить сеть только стендовой Linux VM, сохранив VPN и запреты ролей. Выбор A из ANSWER-5 сохраняется: сначала воспроизводимый четырёхсредный live-стенд, затем test_author.

Подготовка: собственная Debian arm64 VM, Codex0.157.1/Claude2.1.283, UID1000, bubblewrap0.12.0; SSH через собственный Unix/vsock. Только гостевая сеть направлена через SSH/SOCKS и DNS relay loopback хоста. Host VPN/routes и production role-env/профили/guards не менялись. HTTPS вернул200, прямой TCP внутри bwrap --unshare-all запрещён (101). Это проверки зависимостей/транспорта, а не четыре live-доказательства AC17. Исходники и команды: docs/research/live-suite-stand.md в origin/main.

Для Linux Codex обязательный keyring пока сообщает no secret service provider or dbus session found; Claude не авторизован. Подготовка хранилища гостя продолжается. Файловый/API-key fallback для Codex и публикация секретов не разрешены. Реальный provider exec, точечный Unix-допуск, kernel peer/ancestry/lease и все отрицательные контроли четырёх маршрутов остаются обязательными; debug/smoke/manual/skip их не заменяют. До доказанной готовности эскалация AC17 не снимается, платный test_author не перезапускается.

Бюджет остаётся $45, потрачено $40.90, остаток $4.10. Подготовка инфраструктуры не запускала оплачиваемых моделей. Прежний мандат на SPEC/мержи действует только после всех штатных проверок.
