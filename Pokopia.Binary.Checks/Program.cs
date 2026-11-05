using Pokopia.Binary;
using System.Buffers.Binary;
using System.Text;

static void Expect(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}
static MemoryStream Fixture(Action<BinaryWriter> populate)
{
    var stream = new MemoryStream();
    using (var writer = new BinaryWriter(stream, Encoding.ASCII, leaveOpen: true))
        populate(writer);
    stream.Position = 0;
    return stream;
}
static void Text(BinaryWriter writer, string s) =>
    writer.Write(Encoding.ASCII.GetBytes(s));

int failures = 0;
void Check(string name, Action verify)
{
    try { verify(); Console.WriteLine($"PASS {name}"); }
    catch (Exception ex) { failures++; Console.Error.WriteLine($"FAIL {name}: {ex}"); }
}
Check("RDX eight-byte record", () =>
{
    using var data = Fixture(w => { w.Write((ushort)7); w.Write((ushort)2); w.Write(0xe634eeb2u); });
    var rows = RdxReader.Read(data).ToArray();
    Expect(rows.Length == 1 && rows[0].FdataIndex == 7 &&
        rows[0].PlatformFlags == 2 && rows[0].FdataHash == 0xe634eeb2u, "RDX mismatch");
});
Check("RDB standard-13 footer", () =>
{
    using var data = Fixture(w =>
    {
        Text(w, "_DRK0000");
        w.Write(32u); w.Write(0u); w.Write(1u); w.Write(0xabcd1234u);
        w.Write(0UL); // 8 reserved bytes to header size 32
        Text(w, "IDRK0000");
        w.Write(61UL); w.Write(13UL); w.Write(12UL);
        w.Write(0u); w.Write(0x12345678u); w.Write(0x87654321u); w.Write(0u);
        w.Write((ushort)0x0401); w.Write(16u); w.Write(56u);
        w.Write((ushort)0); w.Write((byte)0);
        w.Write(new byte[3]); // pad 61 to 64
    });
    var row = RdbReader.Read(data, 1).Single();
    Expect(row.NameHash == 0x12345678 && row.Offset == 32 &&
        row.FdataOffset == 16 && row.FooterLayout == "standard_13", "RDB mismatch");
});
Check("IDRK bounded metadata", () =>
{
    using var data = Fixture(w =>
    {
        Text(w, "IDRK0000");
        w.Write(64UL); w.Write(8UL); w.Write(8UL);
        w.Write(1u); w.Write(0x1234u); w.Write(0x5678u); w.Write(0u);
        w.Write(new byte[8]); w.Write(new byte[8]);
    });
    var result = IdrkReader.Read(data, 0);
    Expect(result.MetadataLength == 8 && result.PayloadOffset == 56 &&
        result.PackedSize == 8 && result.TypeHash == 0x5678, "IDRK mismatch");
});
Check("KIDSOBJDB IDOK structure", () =>
{
    using var data = Fixture(w =>
    {
        Text(w, "_DOK0000");
        w.Write(28u); w.Write(1u); w.Write(1u); w.Write(0x1234u); w.Write(68u);
        Text(w, "IDOK0000");
        w.Write(40u); w.Write(0xaau); w.Write(0xbbu); w.Write(1u);
        w.Write(5u); w.Write(1u); w.Write(0xccu);
        w.Write(0xdeadbeefu);
    });
    var result = KidsObjDbReader.Inspect(data);
    Expect(result.EntryCount == 1 && result.IdokCount == 1 &&
        result.PartialCount == 0 && result.SampledBlocks[0].SampledProperties[0].ValueBytes == 4,
        "KIDSOBJDB mismatch");
});
Check("TEXINFO count and 104-byte sprites", () =>
{
    using var data = Fixture(w =>
    {
        w.Write(1u);
        byte[] name = new byte[64];
        Encoding.ASCII.GetBytes("item_1425_m").CopyTo(name, 0);
        w.Write(name);
        w.Write(1u);
        foreach (float uv in new float[] {0.1f, 0.2f, 0.3f, 0.2f, 0.1f, 0.4f, 0.3f, 0.4f})
            w.Write(uv);
        w.Write(0u);
    });
    var rec = TexinfoReader.Read(data).Single();
    Expect(rec.Name == "item_1425_m" && rec.TextureLayerRawU32 == 1 &&
        rec.UvStatus == "RECT_OK", "TEXINFO mismatch");
});
Check("triple read and bounded scan", () =>
{
    byte[] data = new byte[0x38];
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(0), 0x9a25ce0cu);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(0x30), 0xd09a60bdu);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(0x34), 0x048fc972u);
    using var stream = new MemoryStream(data);
    var value = NativeHashTriples.ReadAt(stream, 0);
    Expect(value.G1tHash == 0xd09a60bd &&
        NativeHashTriples.Find(stream, 0x9a25ce0cu, 0xd09a60bdu, 0x048fc972u) == 0,
        "Hash triple mismatch");
});
Check("truncated TEXINFO rejected", () =>
{
    using var data = Fixture(w => w.Write(1u));
    try { _ = TexinfoReader.Read(data); }
    catch (InvalidDataException) { return; }
    throw new Exception("Accepted truncated TEXINFO");
});

Phase2Checks.Run(Check);

if (args.Length >= 1)
{
    Check("real original 1333-sprite TEXINFO", () =>
    {
        using var data = File.OpenRead(args[0]);
        var records = TexinfoReader.Read(data);
        Expect(data.Length == 138636 && records.Count == 1333, "Real atlas record count");
        Expect(records.Count(r => r.TextureLayerRawU32 == 0) == 727, "Layer 0 count");
        Expect(records.Count(r => r.TextureLayerRawU32 == 1) == 606, "Layer 1 count");
        Expect(records.Any(r => r.Name == "item_0006"), "Missing item_0006");
    });
}
return failures == 0 ? 0 : 1;
