"""Tests for bounded KT payload streaming (synthetic assets only)."""
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from Scripts.unpack.core import IdrkEntry
from Scripts.unpack.publish_stream import PieceWriter, copy_decoded_stream


class StreamTest(unittest.TestCase):
    def test_raw_stream_and_file_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = b"abcdefghij"
            sink = PieceWriter(Path(tmp), "sample.bin", len(data), chunk_bytes=4, max_single=5)
            header = IdrkEntry(48 + len(data), len(data), len(data), 0, 1, 2, 0, 0)
            copy_decoded_stream(io.BytesIO(data), header, sink)
            self.assertEqual(len(sink.files), 3)
            self.assertEqual(sink.finish(), __import__("hashlib").sha256(data).hexdigest())
            self.assertEqual(b"".join(p.read_bytes() for p in sink.files), data)

    def test_standard_ten_byte_framing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = b"hello-fdata" * 40
            zipped = zlib.compress(original)
            payload = struct.pack("<H", len(zipped)) + bytes(8) + zipped
            header = IdrkEntry(48 + len(payload), len(payload), len(original), 0, 1, 2, 0, 0)
            sink = PieceWriter(Path(tmp), "sample.bin", len(original))
            copy_decoded_stream(io.BytesIO(payload), header, sink)
            sink.finish()
            self.assertEqual(sink.files[0].read_bytes(), original)

    def test_four_byte_framing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = b"compressed-test" * 100
            zipped = zlib.compress(original)
            payload = struct.pack("<I", len(zipped)) + zipped
            header = IdrkEntry(48 + len(payload), len(payload), len(original), 0, 1, 2, 0x100000, 0)
            sink = PieceWriter(Path(tmp), "sample.bin", len(original))
            copy_decoded_stream(io.BytesIO(payload), header, sink)
            sink.finish()
            self.assertEqual(sink.files[0].read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
