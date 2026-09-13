"""Приёмочный тест AC-6 (tasks/01M2CN3VV99BTAJF2JBTNADQPH/SPEC.md):
`orchestrator/fsm_advance.py` не изменён рефакторингом, и
`_discard_out_of_mandate_changes` (:186-279 исходного файла, «Не
входит» SPEC) остаётся побайтно тем же — дедупликация затрагивает
только тройное дублирование трёх WIP-чекпоинтов (AC-1) и разбиение
`_commit_external_step_artifacts` (AC-2), а не эти защищённые куски.

Поведенческая часть AC-6 (фильтр посторонних файлов, конфликт-гвард,
критерий удаления файлов не изменили поведение) покрыта существующим
`tests/test_checkpoint_external_step_artifacts.py`/`tests/
test_checkpoint_zone_filter.py` — зелёность полного набора `tests/`
(AC-3) подтверждает её; здесь проверяется только то, что не покрыто
существующим набором: сам факт нетронутости защищённых кусков байт за
байтом.

Золотые хэши сняты с СЕГОДНЯШНЕГО (дорефакторингового) состояния — тем
состоянием, с которым сверяет сам критерий.

Зелёный с рождения: тест сравнивает сегодняшний код сам с собой —
обязан проходить уже сейчас, красным станет только если рефакторинг
случайно тронет `fsm_advance.py` или тело `_discard_out_of_mandate_
changes` (мутация, которую и требуется ловить).
"""
import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Золотые снимки — sha256 ЛИТЕРАЛОМ, посчитанные с СЕГОДНЯШНЕГО
# (дорефакторингового) дерева при написании этой планки. Намеренно НЕ
# вычисляются заново из текущего файла на каждый запуск — иначе тест
# сравнивал бы файл сам с собой после любой правки и был бы тавтологией,
# зелёной независимо от того, тронут ли защищённый код.
#   sha256(orchestrator/fsm_advance.py):
_FSM_ADVANCE_SHA256 = (
    "1d24f102f261768ff6ff2b6b809f210f9e5d2e3e77a2b4de9210233f18c89327")
#   sha256(исходный текст функции _discard_out_of_mandate_changes,
#   ast.get_source_segment, orchestrator/checkpoint.py):
_DISCARD_OUT_OF_MANDATE_SHA256 = (
    "ca6ea8e3fa1fea101505a15c40fe04790e5e0bcc7db418aa5b1978eabfcb9c71")


def _discard_source_sha256() -> str:
    import ast

    src = (REPO_ROOT / "orchestrator" / "checkpoint.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) \
                and node.name == "_discard_out_of_mandate_changes":
            segment = ast.get_source_segment(src, node)
            return hashlib.sha256(segment.encode("utf-8")).hexdigest()
    raise AssertionError("_discard_out_of_mandate_changes не найдена в AST")


class ProtectedCodeUntouchedTest(unittest.TestCase):

    def test_ac6_fsm_advance_module_is_byte_identical(self):
        """`orchestrator/fsm_advance.py` не изменён ни одним байтом
        рефакторингом R7.

        Ловит мутацию: попутная правка `fsm_advance.py` (например,
        синхронизация импорта под новое имя из `checkpoint.py`,
        прямо запрещённая SPEC требованием 5/«Не входит») — sha256
        файла расходится с золотым снимком.
        """
        actual = hashlib.sha256(
            (REPO_ROOT / "orchestrator" / "fsm_advance.py").read_bytes()
        ).hexdigest()
        self.assertEqual(actual, _FSM_ADVANCE_SHA256)

    def test_ac6_discard_out_of_mandate_changes_body_is_byte_identical(self):
        """Тело `_discard_out_of_mandate_changes` в `orchestrator/
        checkpoint.py` не изменено рефакторингом R7 — SPEC явно
        выводит эту функцию из зоны дедупликации («Не входит»).

        Ловит мутацию: попутное «улучшение» или переразбиение этой
        функции при разборке `_commit_external_step_artifacts` на фазы
        (AC-2) — исходный текст функции по AST расходится с золотым
        снимком, снятым до рефакторинга.
        """
        from orchestrator import checkpoint  # noqa: F401 — сверка импорта

        actual = _discard_source_sha256()
        self.assertEqual(actual, _DISCARD_OUT_OF_MANDATE_SHA256)


if __name__ == "__main__":
    unittest.main()
