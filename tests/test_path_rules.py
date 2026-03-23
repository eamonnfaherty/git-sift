"""Tests for path-based risk classification."""
from git_sift.detector.path_rules import categorize_by_path
from git_sift.models import RiskCategory


def test_security_auth():
    cat, reasons = categorize_by_path("src/auth/login.py")
    assert cat == RiskCategory.SECURITY
    assert any("path" == r.source for r in reasons)


def test_security_secret():
    cat, _ = categorize_by_path("config/secret_key.py")
    assert cat == RiskCategory.SECURITY


def test_security_pem():
    cat, _ = categorize_by_path("certs/server.pem")
    assert cat == RiskCategory.SECURITY


def test_dependencies_requirements():
    cat, _ = categorize_by_path("requirements.txt")
    assert cat == RiskCategory.DEPENDENCIES


def test_dependencies_pyproject():
    cat, _ = categorize_by_path("pyproject.toml")
    assert cat == RiskCategory.DEPENDENCIES


def test_dependencies_package_json():
    cat, _ = categorize_by_path("package.json")
    assert cat == RiskCategory.DEPENDENCIES


def test_infrastructure_dockerfile():
    cat, _ = categorize_by_path("Dockerfile")
    assert cat == RiskCategory.INFRASTRUCTURE


def test_infrastructure_workflow():
    cat, _ = categorize_by_path(".github/workflows/ci.yml")
    assert cat == RiskCategory.INFRASTRUCTURE


def test_infrastructure_terraform():
    cat, _ = categorize_by_path("infra/main.tf")
    assert cat == RiskCategory.INFRASTRUCTURE


def test_migrations():
    cat, _ = categorize_by_path("migrations/0001_initial.py")
    assert cat == RiskCategory.DATABASE_MIGRATIONS


def test_alembic():
    cat, _ = categorize_by_path("alembic/versions/abc123_add_table.py")
    assert cat == RiskCategory.DATABASE_MIGRATIONS


def test_arch_tests():
    cat, _ = categorize_by_path("tests/arch/test_imports.py")
    assert cat == RiskCategory.ARCH_TESTS


def test_existing_tests():
    cat, _ = categorize_by_path("tests/test_user.py")
    assert cat == RiskCategory.EXISTING_TESTS


def test_existing_tests_ts():
    cat, _ = categorize_by_path("src/components/Button.test.tsx")
    assert cat == RiskCategory.EXISTING_TESTS


def test_config_yaml():
    cat, _ = categorize_by_path("config/settings.yaml")
    assert cat == RiskCategory.CONFIG_ENV


def test_config_env():
    cat, _ = categorize_by_path(".env")
    assert cat == RiskCategory.CONFIG_ENV


def test_docs_md():
    cat, _ = categorize_by_path("README.md")
    assert cat == RiskCategory.DOCS_FORMATTING


def test_docs_rst():
    cat, _ = categorize_by_path("docs/api.rst")
    assert cat == RiskCategory.DOCS_FORMATTING


def test_unknown_returns_none():
    cat, reasons = categorize_by_path("src/utils.py")
    assert cat is None
    assert reasons == []


def test_highest_risk_wins_for_security_in_tests():
    # A file that matches both SECURITY (auth) and EXISTING_TESTS (test_*.py)
    cat, reasons = categorize_by_path("tests/test_auth.py")
    # Should return the min (highest risk) = SECURITY
    assert cat == RiskCategory.SECURITY
    # Should have reasons from both matching rules
    assert len(reasons) >= 2


def test_reasons_contain_pattern_and_label():
    cat, reasons = categorize_by_path("requirements.txt")
    assert cat == RiskCategory.DEPENDENCIES
    # requirements.txt matches both requirements*.txt (Dependencies) and *.txt (Docs)
    assert len(reasons) >= 1
    dep_reason = next(r for r in reasons if "requirements" in r.description)
    assert "Dependencies" in dep_reason.description
    assert dep_reason.source == "path"
