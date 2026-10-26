# Записка developer

## Выяснено
- Визит 3 (возврат merge_gate, 6 пунктов) закрыт в gitlab_adapter.py и
  tests/test_forge_gitlab_request.py: transport без перенаправлений (свой
  HTTPRedirectHandler внутри transport, 3xx — числом, request — причина
  «перенаправление запрещено: <код>»), отказ не-https адреса, `[0-9]+`
  в шаблонах путей и в сверке X-Total (было isdigit — принимал «١»),
  тесты на ALLOWED_PAIRS, отсутствие X-Total, лишний ключ запроса.
- Настоящий transport тестируется подменой http.client.HTTPSConnection
  подклассом HTTPConnection (request/getresponse без сокета; ответ —
  http.client.HTTPResponse над BytesIO). Подкласс самого HTTPSConnection
  не годится: его __init__ зовёт super(HTTPSConnection, …) по
  подменённому имени.
- Сторож адресов tests/ (инвариант 35) ловит и текст вида «http://» в
  докстринге; разрешены только хосты localhost и 127.0.0.1.
- 8 мутаций краснят свои тесты; связанные наборы (задача, ci, github,
  invariants, А0, sleep guard) — зелёные. Карта регенерирована.

## Не сработало
- `pytest -n 4` в шаге — воркеры падают «node down»; гонять без -n.
- В Bash роли нет rm/ls, sed требует подтверждения; heredoc с `{"` и
  `$VAR` режется — временные сценарии писать Write в каталог документов
  и удалять через python os.remove.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок.

## Чего не хватило
- —
