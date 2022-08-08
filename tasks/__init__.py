# Python version used in the matrix
supported_python_versions = ["3.7", "3.8", "3.9", "3.10"]
# Python version linked in the '.venv' dev venv, used for quick tests, publish, IDEs, etc
dev_python_version = supported_python_versions[0]

# Project specific
project_folder = "vcrpy_encrypt"
tests_folder = "tests"
tasks_folder = "tasks"

#
# DO NOT CHANGE THE ORDERS OF THESE INSTRUCTIONS
#
# They are needed to avoid circular imports

import tasks.helpers as h  # noqa: E402

ns = h.Collection()
ns.add_collection(h.env)

import tasks.main  # noqa: E402,F401
