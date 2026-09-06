"""Приёмочные тесты задачи 01M1TT9BPBRYMDXXEWVZSRG51V: документная часть
разреза `orchestrator/doctor.py` на пакет — регенерация карты кодовой
базы и путь в `docs/invariants.md` (AC-6, AC-7).

Зелёный с рождения: карта кодовой базы уже свежа на момент написания этих
тестов (перегенерация 06.09 дала только расхождение строки `built_at_sha`,
без содержательного диффа), а `docs/invariants.md` сегодня НЕ называет
`orchestrator/doctor.py` путём (единственное упоминание слова «doctor» в
файле — имя CLI-команды в инварианте 32, не путь к файлу, сверено `grep`
06.09) — актуализировать нечего, условие AC-7 «если называет путём»
сегодня ложно. Оба теста фиксируют эти состояния как инвариант, который
разрез не должен нарушить: AC-6 — регенерацией и сверкой содержимого
(тот же приём, что CI-джоба `codebase-map`, `.github/workflows/ci.yml`),
AC-7 — отсутствием стухшего пути.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

MAP_PATH = REPO_ROOT / "docs" / "codebase-map.md"
INVARIANTS_PATH = REPO_ROOT / "docs" / "invariants.md"


def _without_built_at_sha(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


class CodebaseMapRegeneratedTest(unittest.TestCase):
    """AC-6: `docs/codebase-map.md` регенерирован штатным скриптом после
    разреза — содержимое (без строки `built_at_sha`, которая честно несёт
    sha чужого коммита, см. `.github/workflows/ci.yml` «карта не стухла»)
    совпадает со свежей перегенерацией."""

    def setUp(self):
        self._original = MAP_PATH.read_text(encoding="utf-8")

    def tearDown(self):
        MAP_PATH.write_text(self._original, encoding="utf-8")

    def test_ac6_committed_map_matches_a_fresh_regeneration(self):
        """Прогоняет `python3 scripts/codebase_map.py` (тот же генератор,
        что требует AC-6) и сверяет результат с уже закоммиченным текстом
        карты, игнорируя строку `built_at_sha` (её значение — sha чужого
        коммита, см. комментарий джобы `codebase-map` в
        `.github/workflows/ci.yml`); исходный файл восстанавливается в
        `tearDown` независимо от исхода.

        Ловит мутацию: разработчик перенёс `doctor.py` в пакет `doctor/`,
        но не прогнал `scripts/codebase_map.py` — карта всё ещё описывает
        доктора как один модуль/файл с прежним списком импортируемых
        файлов, перегенерация даёт другое содержимое, и сравнение падает.
        """
        before = _without_built_at_sha(self._original)

        result = subprocess.run(
            [sys.executable, "scripts/codebase_map.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(
            result.returncode, 0,
            f"scripts/codebase_map.py упал: {result.stderr}")

        after = _without_built_at_sha(MAP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            before, after,
            "docs/codebase-map.md отличается от свежей перегенерации — "
            "карта не регенерирована штатным скриптом после разреза")


class InvariantsDocPathTest(unittest.TestCase):
    """AC-7: если `docs/invariants.md` называет `orchestrator/doctor.py`
    путём, путь обновлён на пакет."""

    def test_ac7_invariants_doc_has_no_stale_flat_doctor_path(self):
        """`docs/invariants.md` не содержит устаревший путь
        `orchestrator/doctor.py` — после разреза этого файла (в прежнем
        виде) не существует, а условие критерия («если называет путём —
        обновить») сегодня ложно (файл вообще не называет doctor.py
        путём), так что единственное, что можно и нужно проверить —
        что такая стухшая ссылка не появилась.

        Ловит мутацию: кто-то добавил в `docs/invariants.md` инвариант,
        ссылающийся на `orchestrator/doctor.py` как путь (например,
        скопировав формулировку из старого черновика) вместо актуального
        пути пакета — подстрока находится, тест красный.
        """
        text = INVARIANTS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("orchestrator/doctor.py", text)
