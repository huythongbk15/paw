"""D0 guard for the local-web productization handoff, not runtime evidence."""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_productization_findings_and_packets_are_synchronized():
    for language in (DOCS, DOCS / "vi"):
        audit = (language / "BETA_LIMITATIONS.md").read_text(encoding="utf-8")
        checklist = (language / "EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")
        roadmap = (language / "ROADMAP.md").read_text(encoding="utf-8")
        for number in range(1, 13):
            assert f"F{number:02d}" in audit
        for number in range(15, 37):
            assert f"B-{number}" in checklist
        assert "B-15..B-16" in roadmap
        assert "B-34..B-36" in roadmap
        assert "SPIKE_REQUIRED" in audit
        assert "127.0.0.1" in audit
        assert "CSRF" in audit
        assert "2131" in (language / "IMPLEMENTATION_MAP.md").read_text(encoding="utf-8")


def test_canonical_documents_route_to_productization_contract():
    for language in (DOCS, DOCS / "vi"):
        for name in (
            "README.md", "PRODUCT_CHARTER.md", "ARCHITECTURE.md",
            "IMPLEMENTATION_MAP.md", "ROADMAP.md", "EXECUTION_CHECKLIST.md",
        ):
            text = (language / name).read_text(encoding="utf-8")
            assert "BETA_LIMITATIONS.md" in text, name
            assert "2026-10-05" in text, name
