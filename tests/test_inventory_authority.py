import unittest
from pathlib import Path

from bot_ia.contracts import AuthorityLevel, CanonStatus, SourceStatus
from bot_ia.librarian.inventory import classify_source_metadata, classify_source_type
from bot_ia.librarian.models import SourceType


class InventoryAuthorityTests(unittest.TestCase):
    def test_revised_chapter_is_not_canon_by_filename(self):
        path = Path("One Neko Punch - Cap 1 (revisado).md")
        self.assertIs(classify_source_type(path), SourceType.PLANNING)
        authority, status, canon = classify_source_metadata(path.as_posix(), path)
        self.assertIs(authority, AuthorityLevel.PLAN)
        self.assertIs(status, SourceStatus.VALIDATED)
        self.assertIs(canon, CanonStatus.NON_CANON)

    def test_final_chapter_remains_canon(self):
        path = Path("One Neko Punch - Cap 1 (final).md")
        self.assertIs(classify_source_type(path), SourceType.CHAPTER)
        _, _, canon = classify_source_metadata(path.as_posix(), path)
        self.assertIs(canon, CanonStatus.CANON)


if __name__ == "__main__":
    unittest.main()
