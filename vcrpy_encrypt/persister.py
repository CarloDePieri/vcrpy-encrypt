from abc import ABC
import os
import secrets
import string
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from vcr.serialize import deserialize, serialize


def generate_key(bit_length: int = 128) -> bytes:
    """Utility method to generate a valid aes key as a UTF-8 encoded string. Valid bit_length values are 128, 192
    or 256."""
    if bit_length not in [128, 192, 256]:
        raise ValueError("Invalid bit_length: choose between 128, 192 and 256")
    length = int(bit_length / 8)
    available_chars = string.ascii_uppercase + string.digits + string.ascii_lowercase + string.punctuation
    return "".join(secrets.choice(available_chars) for _ in range(length)).encode("UTF-8")


class NotConfiguredException(RuntimeError):
    """Exception raised when a module configuration key is missing"""


class BaseEncryptedPersister(ABC):
    """VCR custom persister that will encrypt and decrypt cassettes with AES-GCM on disk.

    This class should be extended with a custom encryption_key field."""

    encryption_key: Union[None, bytes] = None
    should_output_clear_text_as_well: bool = False
    clear_text_suffix: str = ""
    encoded_suffix: str = ".enc"

    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """Ensure that an encryption key has been set by the user."""
        if cls.encryption_key is None:
            raise NotConfiguredException("Missing encryption key. Check the documentation!")
        else:
            return cls.encryption_key

    @classmethod
    def load_cassette(cls, cassette_path, serializer):
        try:
            with open(f"{cassette_path}{cls.encoded_suffix}", "rb") as f:
                nonce, tagged_ciphertext = [f.read(x) for x in (12, -1)]
        except OSError:
            raise ValueError("Cassette not found.")
        # decrypt the cassette with aes-gcm
        cipher = AESGCM(cls._get_encryption_key())
        # no Authenticated Associated Data (aad) was used, hence None
        cassette_content = cipher.decrypt(nonce, tagged_ciphertext, None)
        # Check if clear text version is needed
        clear_text_cassette = f"{cassette_path}{cls.clear_text_suffix}"
        if cls.should_output_clear_text_as_well and not os.path.isfile(clear_text_cassette):
            with open(clear_text_cassette, "wb") as f:
                f.write(cassette_content)
        # Deserialize it
        cassette = deserialize(cassette_content, serializer)
        return cassette

    @classmethod
    def save_cassette(cls, cassette_path, cassette_dict, serializer):
        data = serialize(cassette_dict, serializer)
        dirname, _ = os.path.split(cassette_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        # save in clear text if specified
        if cls.should_output_clear_text_as_well:
            with open(f"{cassette_path}{cls.clear_text_suffix}", "w") as f:
                f.write(data)
        # encrypt the cassette with aes-gcm
        cipher = AESGCM(cls._get_encryption_key())
        # make sure the nonce is unique every time
        nonce = os.urandom(12)
        # no Authenticated Associated Data (aad) is needed; cryptography implementation
        # will bundle the tag together with the ciphertext
        tagged_ciphertext = cipher.encrypt(nonce, data.encode(), None)
        # save to the file both the nonce and the budled tag and ciphertext
        with open(f"{cassette_path}{cls.encoded_suffix}", "wb") as f:
            [f.write(x) for x in (nonce, tagged_ciphertext)]
