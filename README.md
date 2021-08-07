[![PyPI](https://img.shields.io/pypi/v/vcrpy-encrypt)](https://pypi.org/project/vcrpy-encrypt/) [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/vcrpy-encrypt)](https://pypi.org/project/vcrpy-encrypt/) [![CI Status](https://img.shields.io/github/workflow/status/CarloDePieri/vcrpy-encrypt/prod?logo=github)](https://github.com/CarloDePieri/vcrpy-encrypt/actions/workflows/prod.yml) [![Coverage Status](https://coveralls.io/repos/github/CarloDePieri/vcrpy-encrypt/badge.svg?branch=main)](https://coveralls.io/github/CarloDePieri/vcrpy-encrypt?branch=main) [![Maintenance](https://img.shields.io/maintenance/yes/2021)](https://github.com/CarloDePieri/vcrpy-encrypt/)

Encrypt vcrpy cassettes so they can be safely kept under version control.

## Rationale

Sensitive data can easily end up in HTTP requests/responses during testing.
[Vcrpy](https://vcrpy.readthedocs.io/en/latest/index.html) has
[a way to scrub that data](https://vcrpy.readthedocs.io/en/latest/advanced.html#filter-sensitive-data-from-the-request)
from its cassettes, but sometimes the tests that logged them actually need that information to pass.

This would normally result in a choice: either don't record those test cassettes or don't keep them under version
control so that they can remain local only.

Enters vcrpy-encrypt: at its core it's a simple
[vcrpy persister](https://vcrpy.readthedocs.io/en/latest/advanced.html#register-your-own-cassette-persister) that will
encrypt cassettes before writing them to disk and decrypt them before replaying them when needed by a test. This means
that tests can replay cassettes with sensitive data in them AND those cassettes can now be safely kept under version
control and shared with others.

## Install

Simply run:

```bash
pip install vcrpy-encrypt
```

## Usage

### Provide a secret key

A secret key is needed to encrypt cassettes. It must be a 128, a 192 or a 256 bits long `bytes` object. vcrpy-encrypt
offers an easy way to generate a random key:

```bash
python -c "from vcrpy_encrypt import generate_key; print(generate_key())"
```

By default this will result in a 128 bits key, but `generate_key` can take `128` or `192` or `256` as argument to
generate a longer key.

If a specific key is preferred, it can be converted from an utf-8, 16/24/32 characters long string like this:

```python
key = "sixteensecretkey".encode("UTF-8")  # len(b'sixteensecretkey') == 16
```

No matter the source, the key must be kept secret and separated from the code under version control!

### Register the persister

Vcrpy's custom persister api needs a class reference. This class can be defined inheriting from
`BaseEncryptedPersister` like this:

```python
from vcrpy_encrypt import BaseEncryptedPersister

key = ...  # recover the secret key from somewhere safe

class MyEncryptedPersister(BaseEncryptedPersister):
    # the encryption_key field must be initialized here with the chosen key
    encryption_key: bytes = key
```

The encrypted persister can now be registered and used:

```python
import vcr
import requests

# create a custom vcr object
my_vcr = vcr.VCR()

# register the encrypted persister into the custom vcr object
my_vcr.register_persister(MyEncryptedPersister)

# use that custom vcr object with use_cassette
with my_vcr.use_cassette("encoded-cassette"):
    # this request will produce an encrypted cassette and will replay it on following runs
    requests.get("https://localhost/?key=super-secret")
```

Keep in mind that multiple vcr objects can coexists, so it's possible to use the default vcr everywhere while
reserving the one with the encrypted persister only for requests resulting in cassettes with sensitive data.

## Customization

Sometimes it can be handy to inspect the content of a cassette. This can be done even when using encrypted cassettes:

```python
class MyEncryptedPersister(BaseEncryptedPersister):
    encryption_key: bytes = key
    should_output_clear_text_as_well = True
```

This persister will output a clear text cassette side by side with the encrypted one. Remember to blacklist all clear
text cassette in the version control system! For example this will cause git to ignore all `.yaml` file inside a
cassettes' folder (at any depth):

```bash
# file: .gitignore
**/cassettes/**/*.yaml
```
Clear text cassettes are only useful for human inspection: the persister will still use only the encrypted ones to
replay network requests.

If different cassettes file name suffix are desired, they can be customized:

```python
class MyEncryptedPersister(BaseEncryptedPersister):
    encryption_key: bytes = key
    should_output_clear_text_as_well = True
    clear_text_suffix = ".custom_clear"
    encoded_suffix = ".custom_enc"
```

## Encryption performance

Currently this library is encrypting cassettes using [cryptography](https://cryptography.io/) with [AES-GCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM). This algorithm
implementation is striking a good balance between security and performance.

Keep in mind that key length will have an impact on encrypt time: 128 bits keys should suffice for most use cases.

## Development

Install [invoke](http://pyinvoke.org/) and [poetry](https://python-poetry.org/):

```bash
pip install invoke poetry
```

Now clone the git repo:

```bash
git clone git@github.com:CarloDePieri/vcrpy-encrypt.git
cd vcrpy-encrypt
inv install
```

This will try to create a virtualenv based on `python3.7` and install there all
project's dependencies. If a different python version is preferred, it can be
selected by specifying  the `--python` (`-p`) flag like this:

```bash
inv install -p python3.8
```

The test suite can be run with commands:

```bash
inv test         # run the test suite
inv test-spec    # run the tests while showing the output as a spec document
inv test-cov     # run the tests suite and produce a coverage report
```

To run the test suite against all supported python version (they must be in path!) run:

```bash
inv test-all-python-version
```

To test the github workflow with [act](https://github.com/nektos/act):

```bash
# First you need a .secrets file - do not version control this!
echo "repo_token: your_coveralls_token" > .secrets

# Then you can run one of these:
inv act-prod           # test the dev workflow
inv act-prod -c shell  # open a shell in the act container (the above must fail first!)
inv act-prod -c clean  # stop and delete a failed act container
```
