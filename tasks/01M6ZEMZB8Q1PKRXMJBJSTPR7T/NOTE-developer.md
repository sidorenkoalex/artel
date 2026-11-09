# Записка developer — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Реализация: config.py (PYCACHE_TEMPLATES_ENV/DIR, pycache_templates_dir, два предела),
  acceptance.py (блок «шаблон байткода» после _place_env; _place_env стал генератором
  contextmanager, наполняет префикс у раннера пульта при run_dir; _own_env наполняет сам
  при run_dir), tests/sandbox.py (константа + os.environ рядом с MODELS_LOCAL).
- Полные прогоны пульта передают argv[0] в _place_env(profile, root, argv[0]).
- Долгоживущие файлы: rules 66/66, runs 22/22 (≈62 с) зелёные.

## Не сработало
- —

## Где остановился
- Гоняю sandbox_place, залоченный pycache-тест и соседние тесты acceptance; затем PLAN.

## Чего не хватило
- —
