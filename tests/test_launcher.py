import unittest
from unittest.mock import patch, MagicMock
import sys
import run


class TestLauncher(unittest.TestCase):
    def test_check_python_version_valid(self):
        with patch.object(sys, "version_info", (3, 10, 0)):
            self.assertTrue(run.check_python_version())

    def test_check_python_version_invalid(self):
        with patch.object(sys, "version_info", (3, 9, 0)):
            self.assertFalse(run.check_python_version())

    def test_check_dependencies_all_present(self):
        with patch.dict(
            sys.modules,
            {
                "PyQt6": MagicMock(),
                "sympy": MagicMock(),
                "matplotlib": MagicMock(),
                "numpy": MagicMock(),
            },
        ):
            self.assertTrue(run.check_dependencies())

    def test_check_dependencies_missing(self):
        with patch("builtins.__import__", side_effect=ImportError("No module named 'PyQt6'")):
            self.assertFalse(run.check_dependencies())

    @patch("builtins.print")
    @patch("subprocess.run")
    def test_install_dependencies_invokes_pip(self, mock_subprocess, mock_print):
        mock_subprocess.return_value = MagicMock(returncode=0)
        success = run.install_dependencies()
        self.assertTrue(success)
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        self.assertEqual(args[1:4], ["-m", "pip", "install"])

    @patch("run.check_dependencies", return_value=True)
    @patch("run.check_python_version", return_value=True)
    def test_ensure_environment_fast_path(self, mock_ver, mock_dep):
        self.assertTrue(run.ensure_environment())

    @patch("builtins.print")
    @patch("run.check_python_version", return_value=False)
    def test_ensure_environment_wrong_python(self, mock_ver, mock_print):
        self.assertFalse(run.ensure_environment())


if __name__ == "__main__":
    unittest.main()
