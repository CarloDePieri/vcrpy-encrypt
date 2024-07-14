import os
import pytest
import requests
import vcr

from vcr.serializers import yamlserializer
from vcr.persisters.filesystem import CassetteNotFoundError, CassetteDecodeError

from tests.conftest import test_cassettes_folder

from vcrpy_encrypt import BaseEncryptedPersister, generate_key
from vcrpy_encrypt.persister import NotConfiguredException


class TestTheEncryptedPersister:
    """Test: The Encrypted Persister..."""

    def test_should_raise_an_error_when_using_the_base_persister_directly(self):
        """It should raise an error when using the base persister directly"""
        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(BaseEncryptedPersister)

        cassette_path = f"{test_cassettes_folder}/with_base_persister"
        request_address = "https://google.com/?q=super-secret"

        with pytest.raises(NotConfiguredException):
            with my_vcr.use_cassette(cassette_path):
                requests.get(request_address)

    def test_should_raise_an_error_without_the_encryption_key_set(self):
        """It should raise an error without the encryption key set"""

        class MyPersister(BaseEncryptedPersister):
            """"""

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyPersister)

        cassette_path = f"{test_cassettes_folder}/without_key"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with pytest.raises(NotConfiguredException):
            with my_vcr.use_cassette(cassette_path):
                requests.get(request_address)

    def test_should_encrypt_and_decrypt_with_success_cassettes(self, is_file, is_not_file):
        """It should encrypt and decrypt with success cassettes"""

        class MyPersister(BaseEncryptedPersister):
            encryption_key: bytes = "secretpassword12".encode("UTF-8")

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyPersister)

        cassette_path = f"{test_cassettes_folder}/encoded-only"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        # Check that the cassette has actually been written
        assert is_file(f"{cassette_path}{BaseEncryptedPersister.encoded_suffix}")
        # Ensure the clear text version is not there
        assert is_not_file(f"{cassette_path}{BaseEncryptedPersister.clear_text_suffix}")

        # Read back the cassette and check that it can be played back
        with my_vcr.use_cassette(cassette_path) as cassette:
            from vcr.request import Request
            default_headers = {'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate',
                               'Connection': 'keep-alive', 'User-Agent': 'python-requests/2.26.0'}
            req = Request("GET", request_address, None, default_headers)
            assert cassette.can_play_response_for(req)

    def test_should_be_able_to_output_clear_text_cassette_on_request(self, is_file):
        """It should be able to output clear text cassette on request"""

        class MyClearTextPersister(BaseEncryptedPersister):
            encryption_key = "secretpassword12".encode("UTF-8")
            should_output_clear_text_as_well = True

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyClearTextPersister)

        cassette_path = f"{test_cassettes_folder}/encoded-and-clear"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        # Check that the cassette has actually been written
        assert is_file(f"{cassette_path}{BaseEncryptedPersister.encoded_suffix}")
        # Ensure that the clear text version is there as well
        assert is_file(f"{cassette_path}{BaseEncryptedPersister.clear_text_suffix}")

    def test_should_generate_clear_text_cassette_when_replaying_encrypted_one_if_specified(self, is_file, is_not_file):
        """It should generate clear text cassette when replaying encrypted one if specified"""

        class MyPersister(BaseEncryptedPersister):
            encryption_key: bytes = "secretpassword12".encode("UTF-8")

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyPersister)

        cassette_path = f"{test_cassettes_folder}/delayed_clear"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        # Check that the cassette has actually been written
        assert is_file(f"{cassette_path}{BaseEncryptedPersister.encoded_suffix}")
        # Ensure the clear text version is not there
        assert is_not_file(f"{cassette_path}{BaseEncryptedPersister.clear_text_suffix}")

        class MyClearPersister(BaseEncryptedPersister):
            encryption_key: bytes = "secretpassword12".encode("UTF-8")
            should_output_clear_text_as_well = True

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyClearPersister)

        # Replay the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        # Ensure the clear text version is there now
        assert is_file(f"{cassette_path}{BaseEncryptedPersister.clear_text_suffix}")

    def test_can_customize_the_cassettes_extensions(self, is_file):
        """It can customize the cassettes extensions"""
        class MyPersister(BaseEncryptedPersister):
            encryption_key: bytes = "secretpassword12".encode("UTF-8")
            clear_text_suffix = ".custom_clear"
            encoded_suffix = ".custom_enc"
            should_output_clear_text_as_well = True

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyPersister)

        cassette_path = f"{test_cassettes_folder}/custom_extensions"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        assert is_file(f"{cassette_path}.custom_enc")
        assert is_file(f"{cassette_path}.custom_clear")

    def test_should_raise_a_specific_error_if_the_cassette_is_not_found(self):
        """The encrypted persister should raise a specific error if the cassette is not found."""
        cassette_path = f"{test_cassettes_folder}/not_there"
        with pytest.raises(CassetteNotFoundError):
            BaseEncryptedPersister.load_cassette(cassette_path, yamlserializer)

    def test_should_raise_a_specific_error_if_the_cassette_fails_to_decode(self):
        """The encrypted persister should raise a specific error if the cassette fails to decode."""
        persister = BaseEncryptedPersister
        cassette_path = f"{test_cassettes_folder}/broken"
        if not os.path.isdir(test_cassettes_folder):
            os.mkdir(test_cassettes_folder)
        with open(cassette_path + persister.encoded_suffix, "w+") as f:
            f.write("this is not a valid cassette")
        with pytest.raises(CassetteDecodeError):
            persister.load_cassette(cassette_path, yamlserializer)


class TestTheGenerateKeyFunction:
    """Test: The generate key function..."""

    def test_can_only_generate_key_of_the_correct_length(self):
        """It can only generate key of the correct length"""
        assert len(generate_key()) == 16
        assert len(generate_key(192)) == 24
        assert len(generate_key(256)) == 32
        with pytest.raises(ValueError):
            generate_key(3)

    def test_produces_valid_key(self):
        """It produces valid key"""
        class MyRandomKeyPersister(BaseEncryptedPersister):
            # This would be useless in reality, do not do this
            encryption_key = generate_key()

        my_vcr = vcr.VCR(record_mode='once')
        my_vcr.register_persister(MyRandomKeyPersister)

        cassette_path = f"{test_cassettes_folder}/encoded-with-random-key"
        request_address = "https://google.com/?q=super-secret"

        # Write the cassette
        with my_vcr.use_cassette(cassette_path):
            requests.get(request_address)

        # Read back the cassette and check that it can be played back
        with my_vcr.use_cassette(cassette_path) as cassette:
            from vcr.request import Request
            default_headers = {'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate',
                               'Connection': 'keep-alive', 'User-Agent': 'python-requests/2.26.0'}
            req = Request("GET", request_address, None, default_headers)
            assert cassette.can_play_response_for(req)
