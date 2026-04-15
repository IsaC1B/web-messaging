from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from .crypto import HybridCryptoBox


class CryptoBoxTests(SimpleTestCase):
	def test_hybrid_round_trip(self):
		with TemporaryDirectory() as temp_dir:
			temp_path = Path(temp_dir)
			sender = HybridCryptoBox("sender:8000", storage_dir=temp_path)
			receiver = HybridCryptoBox("receiver:8001", storage_dir=temp_path)

			payload = sender.encrypt_for_peer(receiver.public_key_pem, "hola mundo")

			self.assertEqual(receiver.decrypt_payload(payload), "hola mundo")
			self.assertTrue((temp_path / "sender_8000_public.txt").exists())
			self.assertTrue((temp_path / "sender_8000_private.pem").exists())

