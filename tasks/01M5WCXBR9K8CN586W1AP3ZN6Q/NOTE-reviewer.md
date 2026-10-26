## Выяснено
- Итерация 1: approved, замечаний нет. Реестр `forge.IMPLEMENTATIONS = {"github": _GitHub, "gitlab": gitlab_adapter}`; у `_GitHub` нет `project_info` и `token_expiry`, поэтому путь GitHub не изменился.
- Долгоживущие тесты задачи + test_doctor: 149 passed; тесты части 1 и А0: 207 passed; role_refusal, help_registry и sandbox helpers зелёные; карта свежая.

## Не сработало
- `plank-run` отказал: в refs/artifacts нет test_*.py, вся планка — долгоживущие файлы в tests/.

## Где остановился
- REVIEW.md записан, status approved.

## Чего не хватило
- Как прогнать «планку», если она целиком в tests/: plank-run этот случай не покрывает.
