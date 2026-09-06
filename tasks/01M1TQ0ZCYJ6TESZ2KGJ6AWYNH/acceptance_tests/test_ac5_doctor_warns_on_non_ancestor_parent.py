"""Приёмочные тесты AC-5 задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH: `doctor`
предупреждает (`warn`), если родитель первого коммита артефактной
ветки живой задачи не является предком `origin/main`.

Интерфейс `doctor.check_artifact_branch_parent_ancestry(conn) ->
list[Check]` — новая функция, вызываемая НАПРЯМУЮ (не через
`doctor.all_checks`, тем же приёмом, что `BranchFreshnessCheckTest`/
`TaskCounterCheckTest` в `tests/test_doctor.py` зовут свою конкретную
проверку изолированно): `all_checks` тянет за собой `live_smoke`
(реальный `subprocess.Popen(["claude", ...])`) и CLI/keychain-проверки
— звать его без полной подмены окружения означало бы либо дорогой и
хрупкий стенд, либо риск живого вызова CLI из приёмочного теста.
Название и сигнатура — планка ЭТОГО теста (SPEC AC-5 оставляет выбор
между расширением существующей проверки и новой отдельной проверке
разработчику по факту статуса задачи 01M1TQ0X14Y5B3C87WC0Q31PK2 на
момент начала разработки, требование 3): если к тому моменту разумнее
расширить чужую проверку, эта функция может быть тонкой обёрткой над
её кодом — тест проверяет НАБЛЮДАЕМОЕ поведение (какая-то проверка
`doctor` предупреждает про задачу с расходящимся родителем), не то,
как именно оно реализовано внутри.

Красен до реализации: `orchestrator/doctor.py` сегодня не содержит
`check_artifact_branch_parent_ancestry` — вызов падает `AttributeError`
на обоих тестах файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, config, doctor, store  # noqa: E402
from _sandbox import ArtifactBranchOriginSandbox  # noqa: E402


def _insert_live_task(task_id: str) -> None:
    store.insert_task(store.db(), task_id, "Задача",
                      "in_dev", f"task/{task_id.lower()}-x",
                      config.DEFAULT_TARGET, 25.0)


class DoctorWarnsOnNonAncestorParentTest(ArtifactBranchOriginSandbox):

    def test_ac5_warns_when_parent_not_ancestor_of_origin_main(self):
        """Артефактная ветка живой задачи заведена от локального пина
        main (без `origin`, как в инциденте 06.09), а `origin/main`
        впоследствии заменяется историей, вообще не связанной с этим
        пином (`make_origin_disjoint`) — родитель первого коммита ветки
        перестаёт быть предком `origin/main`. `doctor` обязан
        предупредить об этой конкретной задаче.

        Ловит мутацию: проверка сравнивает родителя с ТЕКУЩИМ локальным
        `main` вместо `origin/main` (locally тривиально совпадёт и
        никогда не предупредит), либо не фильтрует по «живая задача» и
        падает на отсутствии ветки/задачи — оба варианта не дадут
        `warn` с id этой задачи в списке.
        """
        task_id = "01AC5NONANCESTOR001"
        first_sha = artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": "спек"},
            f"{task_id}: тест")
        self.assertTrue(first_sha, "артефактная ветка не создана")

        self.add_origin(sync=False)
        self.make_origin_disjoint()
        _insert_live_task(task_id)

        checks = doctor.check_artifact_branch_parent_ancestry(store.db())

        self.assertTrue(
            any(c.status == "warn" and task_id in (c.detail or c.name)
                for c in checks),
            f"doctor не предупредил про задачу {task_id} с "
            f"расходящимся родителем артефактной ветки")

    def test_ac5_no_warning_when_parent_is_ancestor_of_origin_main(self):
        """Артефактная ветка живой задачи заведена, когда `origin`
        уже настроен и совпадает с локальным `main` (здоровый случай:
        родитель — предок `origin/main` тривиально, сам себе предок).
        `doctor` не предупреждает про эту задачу.

        Ловит мутацию: проверка предупреждает про КАЖДУЮ живую задачу с
        артефактной веткой независимо от реального предка (всегда
        `warn`) — ложное срабатывание на здоровой задаче.
        """
        task_id = "01AC5HEALTHYANCESTOR2"
        self.add_origin(sync=True)
        first_sha = artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": "спек"},
            f"{task_id}: тест")
        self.assertTrue(first_sha, "артефактная ветка не создана")
        _insert_live_task(task_id)

        checks = doctor.check_artifact_branch_parent_ancestry(store.db())

        self.assertFalse(
            any(c.status == "warn" and task_id in (c.detail or c.name)
                for c in checks),
            f"doctor ложно предупредил про здоровую задачу {task_id}")


if __name__ == "__main__":
    unittest.main()
