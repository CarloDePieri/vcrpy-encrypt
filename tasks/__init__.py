from invoke import Collection

ns = Collection()

# Python version used in the matrix
supported_python_versions = ["3.7", "3.8", "3.9", "3.10"]
# Python version linked in the '.venv' dev venv, used for quick tests, publish, IDEs, etc
dev_python_version = supported_python_versions[0]

# Project specific
project_folder = "vcrpy_encrypt"
tests_folder = "tests"
tasks_folder = "tasks"

# These should stay here, so that names defined before are available in both submodules
import tasks.helpers  # noqa: E402
import tasks.main  # noqa: E402,F401
