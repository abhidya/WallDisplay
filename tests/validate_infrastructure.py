"""Validate the current test infrastructure without assuming aspirational lanes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestInfrastructureValidator:
    """Validate the test infrastructure that actually exists in this repo."""

    def __init__(self):
        self.project_root = project_root
        self.results = {"passed": [], "failed": [], "warnings": []}

    def validate_all(self) -> bool:
        print("🔍 Validating Nano-DLNA Test Infrastructure...\n")

        checks = [
            ("Test Structure", self.check_test_structure),
            ("Test Dependencies Metadata", self.check_dependency_metadata),
            ("Test Factories", self.check_factories),
            ("Test Utilities", self.check_utilities),
            ("Mock Infrastructure", self.check_mocks),
            ("Test Configuration", self.check_configuration),
            ("Execution Entry Points", self.check_test_execution),
            ("Coverage Markers", self.check_coverage_tools),
            ("Performance Test Lane", self.check_performance_tools),
            ("Documentation", self.check_documentation),
        ]

        for check_name, check_func in checks:
            print(f"Checking {check_name}...")
            try:
                check_func()
                self.results["passed"].append(check_name)
                print(f"  ✅ {check_name} - PASSED")
            except AssertionError as exc:
                self.results["failed"].append((check_name, str(exc)))
                print(f"  ❌ {check_name} - FAILED: {exc}")
            except Exception as exc:
                self.results["warnings"].append((check_name, str(exc)))
                print(f"  ⚠️  {check_name} - WARNING: {exc}")
            print()

        return self.print_summary()

    def check_test_structure(self):
        required_dirs = [
            "tests",
            "tests/integration",
            "tests/performance",
            "tests/factories",
            "tests/mocks",
            "tests/utils",
            "web/backend/tests_backend",
            "web/frontend/src/tests",
            "mobile-app/tests",
        ]
        for dir_path in required_dirs:
            path = self.project_root / dir_path
            assert path.exists(), f"Missing directory: {dir_path}"
            assert path.is_dir(), f"Not a directory: {dir_path}"

    def check_dependency_metadata(self):
        tests_requirements = self.project_root / "tests/requirements.txt"
        mobile_package = self.project_root / "mobile-app/package.json"
        assert tests_requirements.exists(), "Missing tests/requirements.txt"
        req_text = tests_requirements.read_text()
        for package in ["pytest", "pytest-cov"]:
            assert package in req_text, f"Missing dependency declaration: {package}"
        assert mobile_package.exists(), "Missing mobile-app/package.json"
        package_json = json.loads(mobile_package.read_text())
        scripts = package_json.get("scripts", {})
        assert "test" in scripts, "Missing mobile test script"
        assert "typecheck" in scripts, "Missing mobile typecheck script"

    def check_factories(self):
        factory_files = [
            "tests/factories/device_factory.py",
            "tests/factories/video_factory.py",
            "tests/factories/overlay_factory.py",
            "tests/factories/session_factory.py",
        ]
        for factory_file in factory_files:
            path = self.project_root / factory_file
            assert path.exists(), f"Missing factory file: {factory_file}"

    def check_utilities(self):
        utils_file = self.project_root / "tests/utils/test_helpers.py"
        assert utils_file.exists(), "Missing tests/utils/test_helpers.py"
        content = utils_file.read_text()

        required_classes = [
            "AsyncTestHelper",
            "DatabaseTestHelper",
            "NetworkTestHelper",
            "FileTestHelper",
            "MockHelper",
        ]
        for class_name in required_classes:
            assert f"class {class_name}" in content, f"Missing utility class: {class_name}"

    def check_mocks(self):
        mock_files = [
            "tests/mocks/device_mocks.py",
            "tests/mocks/dlna_mocks.py",
            "tests/mocks/streaming_mocks.py",
        ]
        for mock_file in mock_files:
            path = self.project_root / mock_file
            assert path.exists(), f"Missing mock file: {mock_file}"

    def check_configuration(self):
        config_files = [
            ("pytest.ini", ["testpaths", "python_files"]),
            ("pyproject.toml", ["[tool.pytest.ini_options]", "--cov"]),
            ("tests/conftest.py", ["pytest", "fixture"]),
            ("web/backend/tests_backend/conftest.py", ["pytest", "fixture"]),
        ]
        for config_file, required_content in config_files:
            path = self.project_root / config_file
            assert path.exists(), f"Missing config file: {config_file}"
            content = path.read_text()
            for required in required_content:
                assert required in content, f"Missing '{required}' in {config_file}"

    def check_test_execution(self):
        run_tests = self.project_root / "run_tests.sh"
        assert run_tests.exists(), "Missing run_tests.sh"
        assert os.access(run_tests, os.X_OK), "run_tests.sh is not executable"

        backend_python = self.project_root / "web/backend/venv/bin/python"
        assert backend_python.exists(), "Missing backend test interpreter"

        # Current reality: mobile tests are the most reliable automated lane.
        mobile_test_files = [
            self.project_root / "mobile-app/tests/control-plane.test.mjs",
            self.project_root / "mobile-app/tests/feature-remote-contracts.test.mjs",
        ]
        for test_file in mobile_test_files:
            assert test_file.exists(), f"Missing mobile test file: {test_file.relative_to(self.project_root)}"

    def check_coverage_tools(self):
        pyproject = self.project_root / "pyproject.toml"
        content = pyproject.read_text()
        assert "--cov=nanodlna" in content, "nanodlna coverage flag missing"
        assert "--cov=web.backend" in content, "web.backend coverage flag missing"

    def check_performance_tools(self):
        perf_test_file = self.project_root / "tests/performance/test_load.py"
        assert perf_test_file.exists(), "Missing performance test file"

    def check_documentation(self):
        required_docs = ["tests/README.md", "tests/TEST_INFRASTRUCTURE.md"]
        for doc_file in required_docs:
            path = self.project_root / doc_file
            assert path.exists(), f"Missing documentation: {doc_file}"
            assert len(path.read_text()) > 100, f"Documentation {doc_file} appears incomplete"

    def print_summary(self) -> bool:
        print("\n" + "=" * 60)
        print("TEST INFRASTRUCTURE VALIDATION SUMMARY")
        print("=" * 60)

        total = sum(len(self.results[key]) for key in self.results)
        print(f"\nTotal Checks: {total}")
        print(f"✅ Passed: {len(self.results['passed'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"⚠️  Warnings: {len(self.results['warnings'])}")

        if self.results["failed"]:
            print("\nFailed Checks:")
            for check_name, error in self.results["failed"]:
                print(f"  - {check_name}: {error}")

        if self.results["warnings"]:
            print("\nWarnings:")
            for check_name, warning in self.results["warnings"]:
                print(f"  - {check_name}: {warning}")

        print("\n" + "=" * 60)
        if self.results["failed"]:
            print("❌ VALIDATION FAILED - Please fix the issues above")
            return False

        print("✅ VALIDATION PASSED - Test infrastructure is ready!")
        return True


if __name__ == "__main__":
    validator = TestInfrastructureValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)
