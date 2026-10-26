---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответы сессии при Операторе (права волны G) на батч В-1…В-5 автора тестов (acceptance_tests/markers.py), 26.10.2026.

- **В-1: A.** `gitlab_adapter.transport(method, url, headers, body, timeout) -> (код: int, заголовки: dict, тело: bytes)`; 4xx/5xx — числом, не исключением; отказ сети — `urllib.error.URLError`, таймаут — `TimeoutError`; функция запроса зовёт транспорт через атрибут модуля (подмена `monkeypatch.setattr(gitlab_adapter, "transport", …)` видна); `body` — JSON в bytes или None; заголовки ответа — имена GitLab (`X-Total`, `X-Next-Page`).
- **В-2: A.** `gitlab_adapter.request(target: str, method: str, path: str, body: dict | None = None)`; `path` — путь под `/api/v4` с id проекта (путь проекта из `url` записи, `/` кодируется `%2F`), строка запроса при нужде; отказ пары — возврат с текстом, где есть метод и путь, без исключения и без вызова транспорта; правка заголовка MR сверяется с текущим заголовком (чтение MR до правки разрешено), отказ — без `PUT`.
- **В-3: A.** `forge.project_info(target)` и `forge.branch_pipeline(target, branch)`; для github — именованный отказ «не реализовано для github», `gh` не вызывается.
- **В-4: A.** При `expires_at: null` в результате `token_expiry` есть текст «без срока» и нет даты.
- **В-5: B.** `urllib.parse` (разбор и кодирование адреса без сети) допустим вне транспорта; `urllib.request`, `http.client`, `socket` и любые сетевые вызовы — только внутри `transport`; `urllib.error` — допустим для разбора исключений. Сторож AC-17 проверяет именно это.

Эти контракты дополняют SPEC; разработчик реализует их буквально.
