"""AC-3 (tasks/T058/SPEC.md): `isolation_smoke` в `doctor` остаётся `ok`
в здоровой конфигурации после расширения новым маркером project-хука.

Требование 2 SPEC называет расширяемую функцию по имени
(`orchestrator/doctor.py: isolation_smoke`) и её ожидаемое поведение
(«канарейка ... не исполняется в окружении роли; та же канарейка в
операторском окружении ... исполняется»); сам механизм различения
(SPEC, требование 1) — выбор PLAN'а, поэтому тест не переоткрывает
внутреннее устройство новой проверки (тем более что она ещё не
написана — эту задачу первым пишет developer после test_author) и не
изобретает точку мокинга под неё. Наблюдаемая, гарантированная
контрактом `Check`-точка — единственное, что можно зафиксировать здесь
не гадая: расширенный `isolation_smoke()` обязан оставаться `ok` в уже
существующей чистой песочнице (тот же приём, что и
`tests/test_doctor.py::IsolationSmokeTest.test_clean_isolation_passes`,
которую этот критерий явно цитирует словами «остаётся ok в здоровой
конфигурации»). Дискриминирующую половину критерия («канарейка
исполняется/не исполняется») в этой же здоровой конфигурации напрямую
и без предположений о внутреннем устройстве проверяют AC-1/AC-2
(`test_ac1_ac2_role_hook_isolation.py`) — они гоняют настоящий `claude`
CLI против настоящей канарейки через реально построенные аргументы шага
роли, а не через `isolation_smoke()`.
"""
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class IsolationSmokeStaysOkTest(TmpRootTest):
    """`isolation_smoke()` читает промпт роли из `config.ROOT / "skills"`
    (её собственный, не Т058-специфичный, путь построения промпта) —
    без копии `skills/` в песочницу проверка падает ещё до канарейки
    project-хука (тот же минимум, что `tests/test_doctor.py`
    `_DoctorTmpRootTest.setUp`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")

    def test_ac3_isolation_smoke_is_ok_in_healthy_configuration(self):
        check = doctor.isolation_smoke()

        self.assertEqual(
            check.status, "ok",
            f"isolation_smoke сообщил не-ok в заведомо здоровой "
            f"конфигурации после расширения маркером project-хука "
            f"(SPEC T058 AC-3): {check.detail}")


if __name__ == "__main__":
    unittest.main()
