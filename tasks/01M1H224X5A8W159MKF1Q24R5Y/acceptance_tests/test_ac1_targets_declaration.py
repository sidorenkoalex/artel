"""AC-1: `targets.yaml` несёт запись `artel` (forge, url, base, token_slot,
no_paths, merge_gate) без ветвления «особый случай» в коде, который её
разбирает (`orchestrator/targets.py`).

Зелёный с рождения: на момент написания этих тестов `orchestrator/
targets.py` уже не несёт ни одной ветки вида `if name ==
config.DEFAULT_TARGET` (разбор общий для любой записи), а боевой
`targets.yaml` уже объявляет `artel` полной записью со всеми полями
FIELDS — AC-1 (требование 1 SPEC) в этой части уже выполнено
предыдущей работой над M1/B1b. Тесты здесь фиксируют это ПОВЕДЕНИЕ
(регрессионный лок): случайный откат к особому случаю (`if name ==
"artel": return`/пропуск проверки для артели, порча записи в
targets.yaml) красит их.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, targets  # noqa: E402


class RealTargetsYamlDeclaresArtelTest(unittest.TestCase):
    """Проверка боевого `targets.yaml` репозитория (не песочницы)."""

    def test_ac1_artel_is_a_full_target_record(self):
        """Боевой targets.yaml несёт запись `artel` со всеми полями FIELDS
        (forge, url, base, token_slot, no_paths, merge_gate) валидного
        вида, разобранную БЕЗ отказа `targets.TargetsError`.

        Ловит мутацию: из записи `artel` в targets.yaml убрали обязательное
        поле (например `merge_gate`) или снова добавили строковую пометку
        «особый случай» вместо полноценного значения — `targets.load()`
        упадёт `TargetsError`, тест покраснеет.
        """
        entries = targets.load()

        self.assertIn(config.DEFAULT_TARGET, entries)
        entry = entries[config.DEFAULT_TARGET]
        for field in ("forge", "url", "base", "token_slot", "no_paths",
                     "merge_gate"):
            self.assertIn(field, entry, f"поле '{field}' отсутствует в "
                          f"записи '{config.DEFAULT_TARGET}'")
        self.assertEqual(entry["forge"], "github")
        self.assertEqual(entry["merge_gate"], "operator")


class NoSpecialCaseInTargetsParsingTest(unittest.TestCase):
    """`orchestrator/targets.py::check` не различает записи по имени —
    невалидная запись 'artel' отказывает ТАК ЖЕ, как невалидная запись
    любого другого имени (иначе особый случай для артели по имени всё
    ещё жил бы в коде разбора, вопреки AC-1)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # `targets.py` читает ровно один файл (`config.TARGETS`), больше
        # ничего не трогает — полноценная ROOT-песочница не нужна.
        self.targets_path = Path(tmp.name) / "targets.yaml"
        patcher = mock.patch.object(config, "TARGETS", self.targets_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, entries_yaml: str) -> None:
        self.targets_path.write_text(f"targets:\n{entries_yaml}",
                                     encoding="utf-8")

    def test_ac1_invalid_artel_entry_fails_the_same_way_as_any_other_name(self):
        """Запись 'artel' без обязательного поля `merge_gate` отказывает
        `TargetsError` — тем же исходом, что и запись стороннего имени
        `sled` с тем же дефектом (одна и та же ошибка по существу: «нет
        поля merge_gate»), без специального прощения по имени 'artel'.

        Ловит мутацию: в `targets.check`/`targets.load` вернулась ветка
        вида `if name == config.DEFAULT_TARGET: return` (или `continue`)
        ДО проверки полноты полей — тогда невалидная запись 'artel' молча
        проходит, тест красный ('artel' не бросает TargetsError, хотя
        должен).
        """
        broken_entry = ("""  {name}:
    forge: github
    url: https://example.invalid/x
    base: main
    token_slot: x-token
    no_paths: []
    project_skills: []
""")
        self._write(broken_entry.format(name=config.DEFAULT_TARGET))
        with self.assertRaises(targets.TargetsError) as ctx_artel:
            targets.load()

        self._write(broken_entry.format(name="sled"))
        with self.assertRaises(targets.TargetsError) as ctx_other:
            targets.load()

        self.assertIn("merge_gate", str(ctx_artel.exception))
        self.assertIn("merge_gate", str(ctx_other.exception))

    def test_ac1_valid_artel_entry_loads_without_special_casing(self):
        """Полностью валидная запись 'artel' разбирается `targets.load()`
        обычным путём — без исключений, ключ 'artel' присутствует.

        Ловит мутацию: код разбора требует для 'artel' ДОПОЛНИТЕЛЬНОЕ,
        отличное от других имён условие (например особый список полей),
        которого валидная запись этого теста не несёт — `load()` упадёт.
        """
        self._write("""  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
""")

        entries = targets.load()

        self.assertIn("artel", entries)
        self.assertEqual(entries["artel"]["merge_gate"], "operator")


if __name__ == "__main__":
    unittest.main()
