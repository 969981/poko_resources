using Pokopia.Binary;
using System.Buffers.Binary;
using System.Text;

public static class Phase2Checks
{
    private static MemoryStream Fixture(Action<BinaryWriter> populate)
    {
        var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, Encoding.ASCII, leaveOpen: true))
            populate(writer);
        stream.Position = 0;
        return stream;
    }

    private static void Magic(BinaryWriter writer, string text) =>
        writer.Write(Encoding.ASCII.GetBytes(text));

    private static void Expect(bool ok, string detail)
    {
        if (!ok) throw new Exception(detail);
    }

    public static void Run(Action<string, Action> check)
    {
        check("KIDS fields: exact raw offsets, hashes, widths, values, RDOK skip", () =>
        {
            using var data = Fixture(w =>
            {
                Magic(w, "_DOK0000");
                w.Write(28u); w.Write(1u); w.Write(2u); w.Write(0u); w.Write(116u);
                Magic(w, "IDOK0000");
                w.Write(60u); w.Write(0xabcdef01u); w.Write(0x12345678u); w.Write(2u);
                w.Write(5u); w.Write(2u); w.Write(0xaau);
                w.Write(8u); w.Write(1u); w.Write(0xbbu);
                w.Write(0xdeadbeefu); w.Write(42u); w.Write(1.25f);
                Magic(w, "RDOK0000");
                w.Write(28u);
                w.Write(7u); w.Write(7u); w.Write(7u); w.Write(0u);
            });
            var rows = KidsFieldReader.Read(data).ToArray();
            Expect(rows.Length == 2, "wrong number of IDOK properties");
            Expect(rows[0].BlockIndex == 0 && rows[0].BlockOffset == 28 &&
                rows[0].BlockNameHash == 0xabcdef01 && rows[0].BlockTypeHash == 0x12345678,
                "block metadata mismatch");
            Expect(rows[0].NameHash == 0xaa && rows[0].Count == 2 &&
                rows[0].ValueOffset == 76 && rows[0].ValueBytes == 8 &&
                rows[0].SampleRawHex.SequenceEqual(new[] { "efbeadde", "2a000000" }) &&
                rows[0].SamplePrimitiveValues.SequenceEqual(new[] { "3735928559", "42" }),
                "first field offset or primitive mismatch");
            Expect(rows[1].NameHash == 0xbb && rows[1].ValueOffset == 84 &&
                rows[1].SampleRawHex.Single() == "0000a03f" &&
                rows[1].SamplePrimitiveValues.Single() == "1.25",
                "float primitive mismatch");
        });

        check("KIDS fields: unknown type is explicitly unresolved", () =>
        {
            using var data = Fixture(w =>
            {
                Magic(w, "_DOK0000");
                w.Write(28u); w.Write(0u); w.Write(1u); w.Write(0u); w.Write(64u);
                Magic(w, "IDOK0000");
                w.Write(36u); w.Write(1u); w.Write(2u); w.Write(1u);
                w.Write(99u); w.Write(100000u); w.Write(3u);
            });
            var row = KidsFieldReader.Read(data).Single();
            Expect(row.Status == "UNSUPPORTED_TYPE_OFFSET_UNKNOWN" &&
                row.ValueOffset == -1 && row.SampleRawHex.Count == 0, "unsafe unknown-type offset");
        });

        check("KIDS fields: truncated property values rejected", () =>
        {
            using var data = Fixture(w =>
            {
                Magic(w, "_DOK0000");
                w.Write(28u); w.Write(0u); w.Write(1u); w.Write(0u); w.Write(64u);
                Magic(w, "IDOK0000");
                w.Write(36u); w.Write(1u); w.Write(2u); w.Write(1u);
                w.Write(5u); w.Write(2u); w.Write(3u);
            });
            try { _ = KidsFieldReader.Read(data).ToArray(); }
            catch (InvalidDataException) { return; }
            throw new Exception("truncated value accepted");
        });

        check("RDB/RDX to physical FDATA: header parity and mismatch detection", () =>
        {
            string folder = Path.Combine(Path.GetTempPath(),
                "pokopia-binary-checks-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            try
            {
                using var rdx = Fixture(w =>
                {
                    w.Write((ushort)0); w.Write((ushort)0xffff); w.Write(0xe634eeb2u);
                });
                using var rdb = Fixture(w =>
                {
                    Magic(w, "_DRK0000");
                    w.Write(32u); w.Write(0u); w.Write(1u); w.Write(0u);
                    w.Write(0UL);
                    Magic(w, "IDRK0000");
                    w.Write(61UL); w.Write(13UL); w.Write(12UL);
                    w.Write(1u); w.Write(0x12345678u); w.Write(0x87654321u); w.Write(0u);
                    w.Write((ushort)0x0401); w.Write(16u); w.Write(56u);
                    w.Write((ushort)0); w.Write((byte)0);
                    w.Write(new byte[3]);
                });
                using var fdata = Fixture(w =>
                {
                    w.Write(new byte[16]);
                    Magic(w, "IDRK0000");
                    w.Write(56UL); w.Write(8UL); w.Write(12UL);
                    w.Write(1u); w.Write(0x12345678u); w.Write(0x87654321u); w.Write(0u);
                    w.Write(new byte[8]);
                });
                string path = Path.Combine(folder, "0xe634eeb2.fdata");
                var bytes = fdata.ToArray();
                File.WriteAllBytes(path, bytes);
                var ok = FdataAuditor.Read(rdb, rdx, folder).Single();
                Expect(ok.Status == "VERIFIED_IDRK_HEADER" && ok.Offset == 16,
                    "true header parity not accepted");
                BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(16 + 36, 4), 0u);
                File.WriteAllBytes(path, bytes);
                var failed = FdataAuditor.Read(rdb, rdx, folder).Single();
                Expect(failed.Status == "IDRK_HEADER_MISMATCH",
                    "changed IDRK name hash incorrectly accepted");
                File.Delete(path);
                var missing = FdataAuditor.Read(rdb, rdx, folder).Single();
                Expect(missing.Status == "FDATA_MISSING", "missing FDATA not reported");
            }
            finally { Directory.Delete(folder, recursive: true); }
        });
    }
}
