# Записка spec_auditor — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Итерация 3 (spec_sha 4707250f…): решения гейта Д-1…Д-4 итерации 2 внесены (AC-16 бит, треб. 11/AC-17 хост помощника, AC-15 без формы, AC-18).
- Новая находка: сверка `remote.origin.url` == url записи (треб. 12) краснит стенды доставки target-human: `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:108` (url https://localhost/grp/…), клон из `tests/sandbox.py:1282` (origin — путь к bare), успешные отправки пульта :894, :1247, :1272, :1396, :1586, :1624. SPEC этого не называет.
- Треб. 11 (токен только для хоста записи) против `tests/test_01m545edths47hsb59akc1ez9c_project_token.py:201` (url file://, host пуст) и `:352-374` (ждёт password=токен).
- Треб. 10: неясно, клонирует ли пульт подмодули у записей без token_slot/артели.
- Глобальный конфиг Оператора (insteadOf/sshCommand/hooksPath) отказывает отправке; GIT_CONFIG_GLOBAL для изоляции теперь тоже отказ.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
- Список тестов-стендов target-human, реально отправляющих через gitcmd, — искал grep по `origin_head(task) == stand.head`.
