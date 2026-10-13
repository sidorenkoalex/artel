"""Подполе `min_uses` поля `core_reference` записи `targets.yaml`: проверка записи.

Группа: долгоживущий
Красен до реализации: проверка поля `core_reference` знает только подполя modules/constants_module/constants и отказывает `min_uses` как неизвестному — методы AC-1 падают на TargetsError; методы AC-2 зелены с рождения (неизвестное подполе уже отказывает с именем проекта, поля и подполя) и сторожат, что новая проверка значения не примет неверное.

Проверка записи — чистая функция над словарём: тест зовёт публичную
`targets.check(name, entry)` (её часть — проверка поля `core_reference`)
без песочницы, файл `targets.yaml` не читается и не пишется.
"""
import random
import unittest

from orchestrator import targets

MODULES = ["lib/core.py", "conf/settings.py"]


def entry_with(min_uses=None, *, present=True) -> dict:
    """Запись проекта с полем `core_reference`; `present` — есть ли подполе."""
    setting = {"modules": list(MODULES), "constants_module": "conf/settings.py",
               "constants": ["LIMIT_A"]}
    if present:
        setting["min_uses"] = min_uses
    return {"forge": "github", "url": "file:///nonexistent/proj",
            "base": "main", "token_slot": "proj-token", "no_paths": [],
            "project_skills": [], "merge_gate": "operator",
            "core_reference": setting}


def new_rng() -> tuple[int, random.Random]:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


class MinUsesAcceptedTest(unittest.TestCase):
    """AC-1: целое от 1 до 1000 проходит проверку записи."""

    def test_ac1_integer_from_1_to_1000_passes_check(self):
        """Границы 1 и 1000 и случайные целые между ними проходят `targets.check` без ошибки.

        Сценарий: запись проекта `proj_<случайное>` с `core_reference` и
        подполем `min_uses`, равным 1, 1000, 2, 999 и пяти случайным целым
        из [1, 1000]; та же запись без подполя — тоже без ошибки (контроль).

        Ловит мутацию: подполе `min_uses` не добавлено в известные подполя
        `core_reference` (TargetsError «неизвестное подполе») либо граница
        взята строго (`1 < v`, `v < 1000`) — 1 или 1000 отказывают.
        """
        seed, rng = new_rng()
        name = f"proj_{rng.randrange(1 << 20):x}"
        values = [1, 1000, 2, 999] + [rng.randint(1, 1000) for _ in range(5)]
        for value in values:
            with self.subTest(min_uses=value):
                try:
                    targets.check(name, entry_with(value))
                except targets.TargetsError as exc:
                    self.fail(f"зерно: {seed}; min_uses={value} отклонено: {exc}")
        targets.check(name, entry_with(present=False))


class MinUsesRefusedTest(unittest.TestCase):
    """AC-2: неверное `min_uses` — TargetsError с проектом, полем и подполем."""

    def test_ac2_wrong_min_uses_refused_naming_project_field_and_subfield(self):
        """0, 1001, `true`, `false` и строки — отказ TargetsError.

        Сценарий: запись проекта `proj_<случайное>` с `min_uses`, равным 0,
        1001, True, False, строкам "4", "abc" и строке со случайным
        числом из [1, 1000]; текст каждого отказа содержит имя проекта,
        `core_reference` и `min_uses`.

        Ловит мутацию: проверка значения `isinstance(v, int)` пропускает
        булево (`True` — подкласс `int`, принят как 1), граница
        `0 <= v` или `v <= 1001` принимает 0 или 1001, строка «4»
        приводится `int()` и принимается, либо текст отказа не называет
        подполе `min_uses` (неверное min_uses принято или отказ без адреса).
        """
        seed, rng = new_rng()
        name = f"proj_{rng.randrange(1 << 20):x}"
        values = [0, 1001, True, False, "4", "abc", str(rng.randint(1, 1000))]
        for value in values:
            with self.subTest(min_uses=value):
                with self.assertRaises(targets.TargetsError,
                                       msg=f"зерно: {seed}; min_uses={value!r} принято") as refused:
                    targets.check(name, entry_with(value))
                text = str(refused.exception)
                for part in (name, "core_reference", "min_uses"):
                    self.assertIn(part, text, f"зерно: {seed}; min_uses={value!r}")


if __name__ == "__main__":
    unittest.main()
