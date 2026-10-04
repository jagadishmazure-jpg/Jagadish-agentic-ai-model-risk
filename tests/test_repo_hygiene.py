"""Repository hygiene: complete docs, current outputs, no dates, no real identifiers, no copied framework."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__", ".terraform", "refs", "evidence"}
MD = sorted(p for p in ROOT.rglob("*.md") if not SKIP_PARTS & set(p.parts))
SECTIONS = [
    "Purpose", "Architecture", "How it works", "Key files", "Code excerpts", "Configuration", "Commands",
    "Real output", "Tests and gates", "Guardrails", "Security and governance", "Observability",
    "Failure modes", "Mapping to Azure services", "Limitations", "Interview talking points",
]  # fmt: skip
FULL_DOCS = sorted(
    p for d in ("pillars", "domains", "scenarios", "components", "infra") for p in (ROOT / "docs" / d).glob("*.md") if p.name != "README.md"
)
MONTHS = r"\b(January|February|March|April|June|July|August|September|October|November|December)\b"
SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".tf", ".bicep", ".hcl", ".sh", ".toml", ".jsonl", ".tfvars"}
TEXT_FILES = [p for p in ROOT.rglob("*") if p.is_file() and not SKIP_PARTS & set(p.parts) and p.suffix in SUFFIXES]
CSA_LINK = "https://cloudsecurityalliance.org/research/working-groups/ai-technology-and-risk"


def folders():
    yield from sorted({p.parent for p in ROOT.rglob("*") if p.is_file() and not SKIP_PARTS & set(p.parts)} | {ROOT / "evidence"})


@pytest.mark.parametrize("folder", list(folders()), ids=lambda p: str(p.relative_to(ROOT)) or ".")
def test_every_folder_has_a_readme_with_a_file_table(folder):
    readme = folder / "README.md"
    assert readme.exists(), f"{folder} has no README.md"
    if folder != ROOT:
        assert "| File | What it does |" in readme.read_text()


def test_folder_readmes_list_every_child():
    for readme in ROOT.rglob("README.md"):
        if SKIP_PARTS & set(readme.parts) or readme.parent == ROOT:
            continue
        text = readme.read_text()
        for child in readme.parent.iterdir():
            if child.name in {"README.md", "__pycache__", ".terraform", ".terraform.lock.hcl"}:
                continue
            name = child.name + ("/" if child.is_dir() else "")
            assert f"`{name}`" in text, f"{readme.relative_to(ROOT)} does not list {name}"


def test_no_dates_in_markdown():
    for p in MD:
        t = re.sub(r"@\d{4}-\d{2}-\d{2}(-preview)?", "", p.read_text())
        assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b", t), f"ISO date in {p}"
        assert not re.search(r"(?<![\w$,.])20[1-3]\d(?![\w,.%])", t), f"year in {p}"
        assert not re.search(MONTHS, t), f"month name in {p}"
        assert "Date:" not in t, f"Date line in {p}"


def test_no_todos_or_placeholders():
    for p in MD:
        t = p.read_text()
        for word in ("TODO", "TBD", "FIXME", "lorem ipsum", "coming soon"):
            assert word not in t, f"{word} in {p}"


def test_full_doc_set_exists():
    names = {p.relative_to(ROOT / "docs").as_posix() for p in FULL_DOCS}
    assert len([n for n in names if n.startswith("pillars/")]) == 5
    assert len([n for n in names if n.startswith("domains/")]) == 5
    assert len([n for n in names if n.startswith("scenarios/")]) == 8
    assert len([n for n in names if n.startswith("components/")]) == 10
    assert len([n for n in names if n.startswith("infra/")]) == 5
    for top in ("implementation-guide", "regulatory-mapping", "interview-guide", "best-practices", "architecture", "deployment"):
        assert (ROOT / "docs" / f"{top}.md").exists()


@pytest.mark.parametrize("doc", FULL_DOCS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_full_doc_has_all_sections_in_order(doc):
    t = doc.read_text()
    pos = [t.find(f"## {i}. {s}") for i, s in enumerate(SECTIONS, 1)]
    assert all(x >= 0 for x in pos), [s for s, x in zip(SECTIONS, pos, strict=True) if x < 0]
    assert pos == sorted(pos)
    assert "```mermaid" in t and "<!-- output:" in t
    assert "<!-- code:" in t or "```bash" in t
    for svc in ("Foundry", "Purview", "Azure Policy", "Application Insights"):
        assert svc in t, f"{doc.name} does not map to {svc}"


def test_every_scenario_family_has_a_doc():
    from modelrisk.scenarios.engine import KIND_CONTROLS

    docs = {p.stem for p in (ROOT / "docs/scenarios").glob("*.md")}
    for kind in KIND_CONTROLS:
        assert any(kind.split("-")[0] in d for d in docs), kind


def test_doc_outputs_and_excerpts_are_current():
    r = subprocess.run([sys.executable, "scripts/render_docs.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_secrets_or_real_identifiers():
    guid = re.compile(r"\b(?!00000000-)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
    bad = [re.compile(p, re.I) for p in (r"AccountKey=", r"-----BEGIN", r"client_secret\s*=", r"@gmail\.com", r"meijer", r"datasparx")]
    for p in TEXT_FILES:
        if p.name == "test_repo_hygiene.py":
            continue
        t = p.read_text(errors="ignore")
        assert not guid.search(t), f"GUID-like identifier in {p}"
        for b in bad:
            assert not b.search(t), f"{b.pattern} in {p}"


def test_framework_pdf_is_never_committed():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if f.lower().endswith(".pdf")]
    assert "*.pdf" in (ROOT / ".gitignore").read_text()


def test_csa_is_attributed_and_linked():
    readme = (ROOT / "README.md").read_text()
    assert "Cloud Security Alliance" in readme and CSA_LINK in readme
    for p in (ROOT / "docs/pillars").glob("*.md"):
        if p.name != "README.md":
            assert CSA_LINK in p.read_text(), p


def test_companies_are_fictional():
    readme = (ROOT / "README.md").read_text()
    assert "fictional" in readme
    for company in ("Halcyon Trust Bank", "Bramblewood Mutual", "Cedar Hollow Lending", "Juniper Health Plan", "Marigold Market"):
        assert company in readme


def test_healthcare_doc_has_not_a_medical_device_note():
    assert "Not a medical device" in (ROOT / "docs/domains/healthcare-prior-auth.md").read_text()


def test_changelog_has_only_unreleased():
    versions = re.findall(r"^## (.+)$", (ROOT / "CHANGELOG.md").read_text(), re.M)
    assert versions == ["Unreleased"]


def test_six_adrs_without_date_lines():
    adrs = sorted((ROOT / "docs/adr").glob("0*.md"))
    assert len(adrs) == 6
    for a in adrs:
        t = a.read_text()
        assert "**Status:**" in t and "Date" not in t


def test_root_files_exist():
    for f in ("README.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE"):
        assert (ROOT / f).exists(), f


def test_readme_has_recruiter_section_and_honest_test_count():
    t = (ROOT / "README.md").read_text()
    assert "## At a glance (for recruiters)" in t
    m = re.search(r"\*\*(\d+) automated tests\*\*", t)
    assert m and int(m.group(1)) >= 150
