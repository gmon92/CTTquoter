import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app import load_env_file


class LocalEnvTests(unittest.TestCase):
    def test_reads_plain_and_quoted_values_with_equals(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('# Local configuration\nCTT_ENV_TEST_KEY="example=value"\n', encoding='utf-8')
            with patch.dict(os.environ):
                os.environ.pop('CTT_ENV_TEST_KEY', None)
                load_env_file(path)
                self.assertEqual(os.environ['CTT_ENV_TEST_KEY'], 'example=value')

    def test_exported_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text("CTT_ENV_TEST_KEY='file-value'\n", encoding='utf-8')
            with patch.dict(os.environ, {'CTT_ENV_TEST_KEY': 'shell-value'}):
                load_env_file(path)
                self.assertEqual(os.environ['CTT_ENV_TEST_KEY'], 'shell-value')

    def test_missing_file_is_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            load_env_file(Path(folder) / 'missing.env')

    def test_loads_project_file_when_started_from_another_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'project'
            project.mkdir()
            for name in ('app.py', 'quote_engine.py', 'tomtom_client.py'):
                shutil.copy(Path(__file__).resolve().parent / name, project / name)
            (project / '.env').write_text('CTT_ENV_PROJECT_TEST_KEY=from-project-file\n', encoding='utf-8')
            code = (
                'import sys, os; '
                f'sys.path.insert(0, {str(project)!r}); '
                'import app; '
                'assert os.environ.get("CTT_ENV_PROJECT_TEST_KEY") == "from-project-file"'
            )
            env = os.environ.copy()
            env.pop('CTT_ENV_PROJECT_TEST_KEY', None)
            result = subprocess.run([sys.executable, '-c', code], cwd=folder, env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, 'Project .env was not loaded from another working folder')


if __name__ == '__main__':
    unittest.main()
