from invoke import task


poetry_pypi_testing = "testpypi"

# Supported python version list - these must also be valid executable in your path
supported_python_versions = ["python3.7", "python3.8", "python3.9"]
# Use the minimum python version required by the package
default_python_bin = supported_python_versions[0]


# If the most currently activated python version is desired, use 'inv install -p latest'
@task
def install(c, python=default_python_bin):
    if python == "latest":
        # don't do anything here: poetry will use the default python version
        pass
    else:
        c.run("poetry env use {}".format(python))
    c.run("poetry install")


@task
def rm_venv(c):
    c.run("rm -rf .venv")


# Use this to change quickly python version
@task(rm_venv)
def reinstall(c, python=default_python_bin):
    install(c, python)


@task
def build(c):
    c.run("poetry build")


@task(build)
def publish_coverage(c):
    c.run("poetry run coveralls")


@task(build)
def publish_test(c):
    c.run(f"poetry publish -r {poetry_pypi_testing}")


@task(build)
def publish(c):
    c.run("poetry publish")


@task()
def test(c, s=False, m=None):
    marks = ""
    if m is not None:
        marks = f" -m {m}"
    capture = ""
    if s:
        capture = " -s"
    c.run(f"poetry run pytest{capture}{marks}", pty=True)


@task()
def test_spec(c, m=None):
    marks = ""
    if m is not None:
        marks = f" -m {m}"
    c.run(f"poetry run pytest -p no:sugar --spec{marks}", pty=True)


@task()
def test_all_python_version(c):
    python_version_checked = ""
    for version in supported_python_versions:
        print(f"\n>>> Installing python venv with version: {version}\n")
        reinstall(c, python=version)
        print(f"\n>>> Running tests with version: {version}\n")
        result = c.run("poetry run pytest", pty=True, warn=True)
        if result.ok:
            python_version_checked += f" {version}"
        else:
            print(f"\n>>> Could not test correctly under {version} - stopping here!")
            exit(1)
    print("\n>>> Ok! Restoring default venv\n")
    reinstall(c)
    print(f"\n>>> All test passed! Python version tested:{python_version_checked}")


@task()
def clear_cassettes(c):
    c.run("rm -rf tests/cassettes")
    print("Cleared!")


@task()
def test_cov(c, full=False):
    c.run("mkdir -p coverage")
    marks = ""
    if not full:
        marks = " -m 'not graphical'"
    c.run(
        f"poetry run pytest --cov=vcrpy_encrypt --cov-report annotate:coverage/cov_annotate --cov-report html:coverage/cov_html{marks}", pty=True)


@task(test_cov)
def html_cov(c):
    c.run("xdg-open coverage/cov_html/index.html")


#
# ACT
#
act_dev_ctx = "act-dev-ci"
act_prod_ctx = "act-prod-ci"
act_secrets_file = ".secrets"


@task
def act_prod(c, cmd=""):
    if cmd == "":
        c.run("act -W .github/workflows/prod.yml", pty=True)
    elif cmd == "shell":
        c.run(f"docker exec --env-file {act_secrets_file} -it {act_prod_ctx} bash", pty=True)
    elif cmd == "clean":
        c.run(f"docker rm -f {act_prod_ctx}", pty=True)


@task
def act_dev(c, cmd=""):
    if cmd == "":
        c.run("act -W .github/workflows/dev.yml", pty=True)
    elif cmd == "shell":
        c.run(f"docker exec --env-file {act_secrets_file} -it {act_dev_ctx} bash", pty=True)
    elif cmd == "clean":
        c.run(f"docker rm -f {act_dev_ctx}", pty=True)
