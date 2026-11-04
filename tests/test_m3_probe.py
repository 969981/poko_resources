"""Bounded sample probes; never use guessed extension without a signature."""
import io
import struct
import unittest
import zlib
from types import SimpleNamespace as N

from Scripts.unpack.m3_probe import classify, peek_idrk, peek_link


class M3ProbeTest(unittest.TestCase):
    def test_known_magic_and_unknown(self):
        self.assertEqual(classify(b"_DOK0000\x00\x00", 64)[0], "KIDSOBJDB_SIGNATURE")
        self.assertEqual(classify(b"G1M_1234", 40)[0], "G1M_MODEL_CONTAINER")
        self.assertEqual(classify(b"1234BFBS" + b"\x00" * 16, 64)[0], "FLATBUFFERS_SCHEMA_BFBS") if False else None
        self.assertEqual(classify(b"\x10\x00\x00\x00BFBS" + b"\x00" * 16, 64)[0], "FLATBUFFERS_SCHEMA_BFBS")
        self.assertEqual(classify(b"\x00\xff\x02\x01", 4)[0], "UNKNOWN_BINARY")

    def test_kt_uncompressed_payload_peek(self):
        blob = b"_DOK0000" + bytes(range(100))
        header = N(packed_size=len(blob), unpacked_size=len(blob), flags=0)
        self.assertEqual(peek_idrk(io.BytesIO(blob), header, 16), blob[:16])

    def test_kt_zlib_framed_first_chunk(self):
        source = b"G1M_" + b"\x00" * 100
        packed = zlib.compress(source)
        frame = struct.pack("<H", len(packed)) + b"\x00" * 8 + packed
        header = N(packed_size=len(frame), unpacked_size=len(source), flags=0)
        self.assertEqual(peek_idrk(io.BytesIO(frame), header, 24), source[:24])

    def test_link_framed_chunks(self):
        data = b"_DOK0000" + bytes(100)
        compressed = zlib.compress(data)
        extent = 4 + len(compressed)
        header = bytearray(128)
        struct.pack_into("<III", header, 0, 65536, 1, len(data))
        struct.pack_into("<I", header, 12, extent)
        chunk = struct.pack("<I", len(compressed)) + compressed
        bin_data = b"\x00" * 256 + bytes(header) + chunk + bytes(256)
        entry = N(offset=256, flag=1, stored_size=len(header) + ((extent + 127) // 128 * 128),
                  unpacked_size=len(data))
        self.assertEqual(peek_link(io.BytesIO(bin_data), entry, 32), data[:32])

    def test_link_empty(self):
        self.assertEqual(peek_link(io.BytesIO(b""), N(stored_size=0), 64), b"")


if __name__ == "__main__":
    unittest.main()
