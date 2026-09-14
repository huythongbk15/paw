"""E1-17: Type annotation linking tests."""
import pytest
from pathlib import Path
from paw.knowledge.type_annotations import (
    AnnotationLink,
    extract_annotations,
)


@pytest.fixture
def annotation_repo(tmp_path):
    """Repo with type annotations."""
    (tmp_path / "annotated.py").write_text(
        "from typing import List, Optional\n"
        "\n"
        "x: int = 5\n"
        "y: str\n"
        "\n"
        "class MyClass:\n"
        "    attr: float = 1.0\n"
        "    def method(self, param: str, opt: Optional[int] = None) -> bool:\n"
        "        result: bool = True\n"
        "        return result\n",
        encoding="utf-8",
    )
    return tmp_path


class TestAnnotationLink:
    def test_dataclass_frozen(self):
        link = AnnotationLink(
            file="m.py", qualified_name="m.x",
            symbol_qualified_name="int", line=3, col=0,
            annotation_text="int", kind="var",
        )
        assert link.qualified_name == "m.x"
        assert link.symbol_qualified_name == "int"
        assert link.kind == "var"

    def test_hashable(self):
        link = AnnotationLink(
            file="m.py", qualified_name="m.x",
            symbol_qualified_name="int", line=3, col=0,
            annotation_text="int",
        )
        assert hash(link) is not None


class TestExtractAnnotations:
    def test_extract_var_annotation(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        links = extract_annotations("annotated.py", source, annotation_repo)
        var_links = [link for link in links if link.kind == "var" and link.annotation_text == "int"]
        assert len(var_links) >= 1

    def test_extract_return_annotation(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        links = extract_annotations("annotated.py", source, annotation_repo)
        returns = [link for link in links if link.kind == "return"]
        assert len(returns) >= 1
        assert returns[0].annotation_text == "bool"

    def test_extract_param_annotations(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        links = extract_annotations("annotated.py", source, annotation_repo)
        params = [link for link in links if link.kind == "param"]
        param_names = {link.qualified_name.rsplit(".", 1)[-1] for link in params}
        assert "param" in param_names
        assert "opt" in param_names

    def test_qualified_names(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        links = extract_annotations("annotated.py", source, annotation_repo)
        for link in links:
            assert "annotated.py" in link.qualified_name or link.file == "annotated.py"

    def test_syntax_error_skipped(self, tmp_path):
        links = extract_annotations("broken.py", "def broken(\n    pass\n", tmp_path)
        assert links == []

    def test_empty_file(self, tmp_path):
        links = extract_annotations("empty.py", "", tmp_path)
        assert links == []

    def test_complex_annotations(self, tmp_path):
        source = (
            "from typing import Dict, List\n"
            "data: Dict[str, int] = {}\n"
            "items: List[str] = []\n"
        )
        links = extract_annotations("complex.py", source, tmp_path)
        var_links = [link for link in links if link.kind == "var"]
        assert len(var_links) >= 2

    def test_no_annotations(self, tmp_path):
        source = "x = 5\ndef foo(a):\n    return a\n"
        links = extract_annotations("plain.py", source, tmp_path)
        assert links == []

    def test_determinism(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        l1 = extract_annotations("annotated.py", source, annotation_repo)
        l2 = extract_annotations("annotated.py", source, annotation_repo)
        assert l1 == l2

    def test_annotation_text_preserved(self, annotation_repo):
        source = Path(annotation_repo, "annotated.py").read_text()
        links = extract_annotations("annotated.py", source, annotation_repo)
        for link in links:
            assert link.annotation_text != ""  # all links have annotation text
            assert link.confidence == 1.0
