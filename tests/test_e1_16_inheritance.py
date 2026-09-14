"""E1-16: Inheritance and method resolution tests."""
import pytest
from pathlib import Path
from paw.knowledge.inheritance import (
    ClassInfo,
    InheritanceEdge,
    extract_inheritance,
)


@pytest.fixture
def inheritance_repo(tmp_path):
    """Repo with inheritance hierarchy."""
    (tmp_path / "base.py").write_text(
        "class Base:\n    def method_a(self):\n        pass\n"
        "class Mixin:\n    def mixin_method(self):\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "derived.py").write_text(
        "from base import Base, Mixin\n"
        "class Derived(Base, Mixin):\n    def method_b(self):\n        pass\n",
        encoding="utf-8",
    )
    return tmp_path


class TestClassInfo:
    def test_dataclass(self):
        info = ClassInfo(
            qualified_name="pkg.C", file="pkg/c.py",
            bases=["Base"], methods=[("method_a", 3)], mro=["pkg.C", "pkg.Base"],
        )
        assert info.qualified_name == "pkg.C"
        assert info.bases == ["Base"]
        assert len(info.methods) == 1


class TestInheritanceEdge:
    def test_dataclass_frozen(self):
        edge = InheritanceEdge(
            sub_class="pkg.Derived", sub_file="pkg/derived.py",
            base_class="pkg.Base", base_file="pkg/base.py",
            line=3,
        )
        assert edge.sub_class == "pkg.Derived"
        assert edge.base_class == "pkg.Base"
        assert edge.confidence == 1.0

    def test_hashable(self):
        edge = InheritanceEdge(
            sub_class="pkg.Derived", sub_file="pkg/derived.py",
            base_class="pkg.Base", base_file=None,
            line=3,
        )
        assert hash(edge) is not None


class TestExtractInheritance:
    def test_extract_classes(self, inheritance_repo):
        source = Path(inheritance_repo, "base.py").read_text()
        classes = extract_inheritance("base.py", source, inheritance_repo)
        assert len(classes) == 2
        assert classes[0].qualified_name == "base.Base"
        assert classes[1].qualified_name == "base.Mixin"

    def test_extract_methods(self, inheritance_repo):
        source = Path(inheritance_repo, "base.py").read_text()
        classes = extract_inheritance("base.py", source, inheritance_repo)
        base = next(c for c in classes if c.qualified_name == "base.Base")
        assert base.methods == [("method_a", 2)]

    def test_extract_bases(self, inheritance_repo):
        source = Path(inheritance_repo, "derived.py").read_text()
        classes = extract_inheritance("derived.py", source, inheritance_repo)
        derived = next(c for c in classes if c.qualified_name == "derived.Derived")
        assert set(derived.bases) == {"Base", "Mixin"}

    def test_syntax_error_skipped(self, tmp_path):
        (tmp_path / "broken.py").write_text("class Broken(\n    pass\n", encoding="utf-8")
        classes = extract_inheritance("broken.py", "garbage", tmp_path)
        assert classes == []  # syntax error → empty

    def test_multiple_bases(self, inheritance_repo):
        source = Path(inheritance_repo, "derived.py").read_text()
        classes = extract_inheritance("derived.py", source, inheritance_repo)
        derived = classes[0]
        assert len(derived.bases) == 2

    def test_empty_file(self, tmp_path):
        (tmp_path / "empty.py").write_text("", encoding="utf-8")
        classes = extract_inheritance("empty.py", "", tmp_path)
        assert classes == []

    def test_no_bases_class(self, tmp_path):
        (tmp_path / "simple.py").write_text("class Simple:\n    pass\n", encoding="utf-8")
        classes = extract_inheritance("simple.py", "class Simple:\n    pass\n", tmp_path)
        assert len(classes) == 1
        assert classes[0].bases == []

    def test_determinism(self, inheritance_repo):
        source = Path(inheritance_repo, "base.py").read_text()
        c1 = extract_inheritance("base.py", source, inheritance_repo)
        c2 = extract_inheritance("base.py", source, inheritance_repo)
        assert c1 == c2
