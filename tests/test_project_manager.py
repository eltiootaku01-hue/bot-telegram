from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bot_ia.core.project_manager import ProjectError, ProjectManager


class ProjectManagerTests(unittest.TestCase):
    def test_create_novel_persists_name_and_isolated_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = ProjectManager(root)
            record = manager.create_novel("Problemas de Capibara")

            self.assertEqual(record.project_id, "problemas-de-capibara")
            self.assertEqual(record.display_name, "Problemas de Capibara")
            for directory in ("biblioteca", "memoria", "canon", "historial", "config"):
                self.assertTrue((record.root_path / directory).is_dir())
            self.assertTrue(manager.registry_path.is_file())

            reloaded = ProjectManager(root)
            self.assertEqual(reloaded.get("problemas-de-capibara"), record)

    def test_windows_unsafe_punctuation_is_removed_from_internal_id(self) -> None:
        self.assertEqual(ProjectManager.slugify("¿Oasis o Espejismo?"), "oasis-o-espejismo")

    def test_duplicate_project_is_rejected_without_creating_second_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = ProjectManager(Path(temporary))
            manager.create_novel("Fragmentado")
            with self.assertRaises(ProjectError):
                manager.create_novel("fragmentado")
            self.assertEqual(len(manager.all()), 1)

    def test_empty_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manager = ProjectManager(Path(temporary))
            with self.assertRaises(ProjectError):
                manager.create_novel("   ")


if __name__ == "__main__":
    unittest.main()
