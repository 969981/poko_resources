using Edoke.IO;
using System.Buffers.Binary;
using System.Globalization;
using System.Text;

namespace Pokopia.Binary;

/// <summary>
/// One original IDOK field, with offsets relative to the *decompressed* KIDSOBJDB.
/// The offsets, bytes and primitive representations are evidence, not game semantics.
/// </summary>
public sealed record KidsFieldEvidence(
    int BlockIndex, long BlockOffset, uint BlockSize, uint BlockNameHash,
    uint BlockTypeHash, int PropertyIndex, uint TypeCode, uint Count,
    uint NameHash, long ValueOffset, ulong ValueBytes, string Status,
    IReadOnlyList<string> SampleRawHex, IReadOnlyList<string> SamplePrimitiveValues);

public static class KidsFieldReader
{
    private const uint MaxBlocks = 2_000_000;
    private const uint MaxProperties = 65_536;

    private static int Width(uint type) => type switch
    {
        0 or 1 => 1,
        2 or 3 => 2,
        4 or 5 or 8 => 4,
        10 => 16,
        12 => 8,
        13 => 12,
        _ => -1
    };

    private static string Float(ReadOnlySpan<byte> bytes)
    {
        uint bits = BinaryPrimitives.ReadUInt32LittleEndian(bytes);
        float value = BitConverter.Int32BitsToSingle(unchecked((int)bits));
        return float.IsFinite(value)
            ? value.ToString("R", CultureInfo.InvariantCulture)
            : $"nonfinite:0x{bits:x8}";
    }

    private static string Primitive(uint type, ReadOnlySpan<byte> b) => type switch
    {
        0 => unchecked((sbyte)b[0]).ToString(CultureInfo.InvariantCulture),
        1 => b[0].ToString(CultureInfo.InvariantCulture),
        2 => BinaryPrimitives.ReadInt16LittleEndian(b).ToString(CultureInfo.InvariantCulture),
        3 => BinaryPrimitives.ReadUInt16LittleEndian(b).ToString(CultureInfo.InvariantCulture),
        4 => BinaryPrimitives.ReadInt32LittleEndian(b).ToString(CultureInfo.InvariantCulture),
        5 => BinaryPrimitives.ReadUInt32LittleEndian(b).ToString(CultureInfo.InvariantCulture),
        8 => Float(b),
        10 or 12 or 13 => "[" + string.Join(",", Enumerable.Range(0, b.Length / 4)
            .Select(i => Float(b.Slice(i * 4, 4)))) + "]",
        _ => throw new InvalidDataException("KIDS_UNSUPPORTED_PRIMITIVE")
    };

    /// <summary>
    /// Streaming, read-only field ledger. Unknown types stop *that block's*
    /// value-offset walk; remaining fields are never assigned guessed offsets.
    /// A zero-count property is supported. At most 32 elements per field are sampled.
    /// </summary>
    public static IEnumerable<KidsFieldEvidence> Read(Stream stream, int sampleElements = 8)
    {
        if (!stream.CanRead || !stream.CanSeek || stream.Length < 28 ||
            sampleElements < 0 || sampleElements > 32)
            throw new InvalidDataException("KIDS_FIELDS_INVALID_INPUT");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(0);
        if (Encoding.ASCII.GetString(reader.ReadBytes(8)) != "_DOK0000")
            throw new InvalidDataException("KIDS_FIELDS_BAD_MAGIC");
        uint headerSize = reader.ReadUInt32();
        _ = reader.ReadUInt32(); // Platform, preserved by KidsObjDbReader.Inspect.
        uint blockCount = reader.ReadUInt32();
        _ = reader.ReadUInt32(); // Name-file hash.
        _ = reader.ReadUInt32(); // Advertised size.
        if (headerSize < 28 || headerSize > stream.Length || blockCount > MaxBlocks)
            throw new InvalidDataException("KIDS_FIELDS_BAD_HEADER");
        long at = ((long)headerSize + 3) & ~3L;

        for (int block = 0; block < (int)blockCount; block++)
        {
            if (at > stream.Length - 12)
                throw new InvalidDataException($"KIDS_FIELDS_TRUNCATED_BLOCK:{block}");
            reader.Seek(at);
            string magic = Encoding.ASCII.GetString(reader.ReadBytes(8));
            if (magic != "IDOK0000" && magic != "RDOK0000")
                throw new InvalidDataException($"KIDS_FIELDS_UNKNOWN_BLOCK:{block}");
            uint size = reader.ReadUInt32();
            int minimum = magic == "IDOK0000" ? 24 : 12;
            if (size < minimum || (ulong)size > (ulong)(stream.Length - at))
                throw new InvalidDataException($"KIDS_FIELDS_BAD_SIZE:{block}");
            long end = at + size;

            if (magic == "IDOK0000")
            {
                uint blockName = reader.ReadUInt32();
                uint blockType = reader.ReadUInt32();
                uint propertyCount = reader.ReadUInt32();
                if (propertyCount > MaxProperties || 24UL + (ulong)propertyCount * 12 > size)
                    throw new InvalidDataException($"KIDS_FIELDS_BAD_PROPERTIES:{block}");
                var fields = new (uint Type, uint Count, uint Name)[(int)propertyCount];
                for (int p = 0; p < fields.Length; p++)
                    fields[p] = (reader.ReadUInt32(), reader.ReadUInt32(), reader.ReadUInt32());
                long cursor = reader.Position;
                for (int p = 0; p < fields.Length; p++)
                {
                    var field = fields[p];
                    int width = Width(field.Type);
                    if (width < 0)
                    {
                        yield return new KidsFieldEvidence(block, at, size, blockName, blockType,
                            p, field.Type, field.Count, field.Name, -1, 0,
                            "UNSUPPORTED_TYPE_OFFSET_UNKNOWN", Array.Empty<string>(),
                            Array.Empty<string>());
                        break;
                    }

                    ulong valueBytes = (ulong)field.Count * (uint)width;
                    if (cursor > end || valueBytes > (ulong)(end - cursor))
                        throw new InvalidDataException($"KIDS_FIELDS_TRUNCATED_VALUE:{block}:{p}");
                    int count = (int)Math.Min(field.Count, (uint)sampleElements);
                    reader.Seek(cursor);
                    byte[] raw = reader.ReadBytes(checked(count * width));
                    if (raw.Length != count * width)
                        throw new EndOfStreamException("KIDS_FIELDS_SAMPLE_TRUNCATED");
                    var rawHex = new string[count];
                    var primitive = new string[count];
                    for (int i = 0; i < count; i++)
                    {
                        var element = raw.AsSpan(i * width, width);
                        rawHex[i] = Convert.ToHexString(element).ToLowerInvariant();
                        primitive[i] = Primitive(field.Type, element);
                    }
                    yield return new KidsFieldEvidence(block, at, size, blockName, blockType,
                        p, field.Type, field.Count, field.Name, cursor, valueBytes,
                        "FIXED_WIDTH_RAW_PARSED", rawHex, primitive);
                    cursor += (long)valueBytes;
                }
            }
            at = (end + 3) & ~3L;
            if (at > stream.Length)
                throw new InvalidDataException("KIDS_FIELDS_BLOCK_ALIGNMENT_OVERRUN");
        }
    }
}
