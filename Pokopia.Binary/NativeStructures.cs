using Edoke.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace Pokopia.Binary;

/// <summary>FDATA record framing only; the original Python decoder owns decompression.</summary>
public sealed record IdrkRecord(long Offset, ulong EntrySize, ulong PackedSize, ulong UnpackedSize,
    uint EntryType, uint NameHash, uint TypeHash, uint Flags, long MetadataOffset,
    ulong MetadataLength, long PayloadOffset);

public static class IdrkReader
{
    public static IdrkRecord Read(Stream stream, long offset)
    {
        if (!stream.CanSeek || offset < 0 || offset > stream.Length - 48)
            throw new InvalidDataException("IDRK_OFFSET_OUT_OF_RANGE");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(offset);
        if (Encoding.ASCII.GetString(reader.ReadBytes(8)) != "IDRK0000")
            throw new InvalidDataException("IDRK_BAD_MAGIC");
        ulong entrySize = reader.ReadUInt64();
        ulong packed = reader.ReadUInt64();
        ulong unpacked = reader.ReadUInt64();
        uint type = reader.ReadUInt32();
        uint name = reader.ReadUInt32();
        uint typeHash = reader.ReadUInt32();
        uint flags = reader.ReadUInt32();
        if (entrySize < 48 || entrySize > (ulong)(stream.Length - offset) ||
            packed > entrySize - 48)
            throw new InvalidDataException("IDRK_INVALID_LENGTH");
        ulong metadataLen = entrySize - 48 - packed;
        if (metadataLen > 65536)
            throw new InvalidDataException("IDRK_EXCESSIVE_METADATA");
        long metadataOffset = checked(offset + 48);
        long payloadOffset = checked(metadataOffset + (long)metadataLen);
        return new IdrkRecord(offset, entrySize, packed, unpacked, type, name,
            typeHash, flags, metadataOffset, metadataLen, payloadOffset);
    }
}

public sealed record KidsProperty(uint TypeCode, uint Count, uint NameHash,
    ulong ValueBytes, string Status);
public sealed record KidsBlock(int Index, string Kind, long Offset, uint Size,
    string Status, IReadOnlyList<KidsProperty> SampledProperties, uint[]? RdokRawWords);
public sealed record KidsReport(uint HeaderSize, uint Platform, uint EntryCount,
    uint NameFileHash, uint DeclaredSize, int IdokCount, int RdokCount,
    int PartialCount, int UnsupportedFieldCount, IReadOnlyList<KidsBlock> SampledBlocks,
    IReadOnlyList<string> Warnings);

/// <summary>
/// Bounded structural reader for _DOK0000. Unknown IDOK property types and RDOK
/// semantics are never guessed. Mirrors Scripts/unpack/decode_kidsobjdb.py.
/// </summary>
public static class KidsObjDbReader
{
    private const uint MaxBlocks = 2_000_000;
    private const uint MaxProperties = 65536;

    private static int TypeSize(uint kind) => kind switch
    {
        0 or 1 => 1,
        2 or 3 => 2,
        4 or 5 or 8 => 4,
        10 => 16,
        12 => 8,
        13 => 12,
        _ => -1
    };

    public static KidsReport Inspect(Stream stream, int sampleBlocks = 32, int sampleProperties = 32)
    {
        if (!stream.CanSeek || stream.Length < 28 ||
            sampleBlocks < 0 || sampleProperties < 0)
            throw new InvalidDataException("KIDSOBJDB_INVALID_INPUT");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(0);
        if (Encoding.ASCII.GetString(reader.ReadBytes(8)) != "_DOK0000")
            throw new InvalidDataException("KIDSOBJDB_INVALID_HEADER");
        uint headerSize = reader.ReadUInt32();
        uint platform = reader.ReadUInt32();
        uint entryCount = reader.ReadUInt32();
        uint nameHash = reader.ReadUInt32();
        uint declaredSize = reader.ReadUInt32();
        if (headerSize < 28 || headerSize > stream.Length)
            throw new InvalidDataException("KIDSOBJDB_INVALID_HEADER_SIZE");
        if (entryCount > MaxBlocks) throw new InvalidDataException("KIDSOBJDB_TOO_MANY_BLOCKS");

        long at = ((long)headerSize + 3) & ~3L;
        int idok = 0, rdok = 0, partial = 0, unsupported = 0;
        var samples = new List<KidsBlock>();
        var warnings = new List<string>();

        for (int index = 0; index < entryCount; index++)
        {
            if (at > stream.Length - 12)
                throw new InvalidDataException($"KIDSOBJDB_BLOCK_HEADER_TRUNCATED:{index}");
            reader.Seek(at);
            string magic = Encoding.ASCII.GetString(reader.ReadBytes(8));
            if (magic != "IDOK0000" && magic != "RDOK0000")
                throw new InvalidDataException($"KIDSOBJDB_BLOCK_MAGIC_UNKNOWN:{index}");
            string kind = magic[..4];
            uint size = reader.ReadUInt32();
            int minSize = kind == "IDOK" ? 24 : 12;
            if (size < minSize || size > stream.Length - at)
                throw new InvalidDataException($"KIDSOBJDB_BLOCK_SIZE_INVALID:{index}");
            long end = at + size;
            string status;
            var props = new List<KidsProperty>();
            uint[]? rawWords = null;

            if (kind == "IDOK")
            {
                idok++;
                _ = reader.ReadUInt32(); // property-name hash of block
                _ = reader.ReadUInt32(); // property-type hash of block
                uint propCount = reader.ReadUInt32();
                if (propCount > MaxProperties || 24UL + (ulong)propCount * 12 > size)
                    throw new InvalidDataException($"KIDSOBJDB_PROPERTY_HEADER_INVALID:{index}");
                var fields = new (uint Type, uint Count, uint Hash)[(int)propCount];
                for (int i = 0; i < fields.Length; i++)
                    fields[i] = (reader.ReadUInt32(), reader.ReadUInt32(), reader.ReadUInt32());
                long cursor = reader.Position;
                status = "FIXED_WIDTH_VALUES_PARSED";
                for (int i = 0; i < fields.Length; i++)
                {
                    var field = fields[i];
                    int unit = TypeSize(field.Type);
                    if (unit < 0)
                    {
                        unsupported++;
                        partial++;
                        status = "PARTIAL_UNSUPPORTED_PROPERTY";
                        if (props.Count < sampleProperties && samples.Count < sampleBlocks)
                            props.Add(new KidsProperty(field.Type, field.Count, field.Hash, 0,
                                "UNSUPPORTED_TYPE"));
                        break;
                    }
                    ulong valueBytes = (ulong)field.Count * (uint)unit;
                    if (valueBytes > (ulong)(end - cursor))
                        throw new InvalidDataException($"KIDSOBJDB_PROPERTY_DATA_TRUNCATED:{index}:{i}");
                    cursor += (long)valueBytes;
                    if (props.Count < sampleProperties && samples.Count < sampleBlocks)
                        props.Add(new KidsProperty(field.Type, field.Count, field.Hash, valueBytes,
                            "DECODED_FIXED_WIDTH"));
                }
            }
            else
            {
                rdok++;
                partial++;
                if (size == 28)
                {
                    rawWords = [reader.ReadUInt32(), reader.ReadUInt32(),
                        reader.ReadUInt32(), reader.ReadUInt32()];
                    status = "RDOK_WORDS_UNINTERPRETED";
                }
                else status = "RDOK_OPAQUE";
            }
            if (samples.Count < sampleBlocks)
                samples.Add(new KidsBlock(index, kind, at, size, status, props, rawWords));
            at = (end + 3) & ~3L;
            if (at > stream.Length)
                throw new InvalidDataException("KIDSOBJDB_ALIGNED_BLOCK_OVERRUN");
        }

        if (at != stream.Length)
            warnings.Add($"UNACCOUNTED_TRAILING_BYTES:{stream.Length - at}");
        if (declaredSize != 0 && declaredSize != stream.Length)
            warnings.Add($"DECLARED_SIZE_MISMATCH:{declaredSize}:{stream.Length}");
        return new KidsReport(headerSize, platform, entryCount, nameHash,
            declaredSize, idok, rdok, partial, unsupported, samples, warnings);
    }
}

public sealed record TexinfoRecord(int RecordIndex, string Name, uint TextureLayerRawU32,
    float[] UvCorners, uint RecordTailRawU32, string UvStatus);

/// <summary>Exactly count * 104 + 4 bytes, matching g1t_to_png.parse_texinfo().</summary>
public static partial class TexinfoReader
{
    [GeneratedRegex("^[A-Za-z0-9_./-]{1,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex ValidName();

    public static IReadOnlyList<TexinfoRecord> Read(Stream stream)
    {
        if (!stream.CanSeek || stream.Length < 4)
            throw new InvalidDataException("TEXINFO_TRUNCATED_HEADER");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(0);
        uint count = reader.ReadUInt32();
        if (count is < 1 or > 65536 || stream.Length != 4L + 104L * count)
            throw new InvalidDataException($"TEXINFO_COUNT_SIZE_MISMATCH:{count}:{stream.Length}");
        var result = new List<TexinfoRecord>((int)count);
        for (int i = 0; i < count; i++)
        {
            byte[] rawName = reader.ReadBytes(64);
            int length = Array.IndexOf(rawName, (byte)0);
            if (length < 0) length = rawName.Length;
            if (length == 0 || rawName.AsSpan(0, length).IndexOfAnyInRange((byte)128, byte.MaxValue) >= 0)
                throw new InvalidDataException($"TEXINFO_NON_ASCII_OR_EMPTY_NAME:{i}");
            string name = Encoding.ASCII.GetString(rawName, 0, length);
            if (!ValidName().IsMatch(name))
                throw new InvalidDataException($"TEXINFO_INVALID_NAME:{i}:{name}");
            uint layer = reader.ReadUInt32();
            float[] uv = new float[8];
            for (int j = 0; j < uv.Length; j++)
            {
                uv[j] = reader.ReadSingle();
                if (!float.IsFinite(uv[j]))
                    throw new InvalidDataException($"TEXINFO_NONFINITE_UV:{i}");
            }
            uint tail = reader.ReadUInt32();
            bool rect = Math.Abs(uv[1] - uv[3]) < 1e-5 &&
                        Math.Abs(uv[0] - uv[4]) < 1e-5 &&
                        Math.Abs(uv[2] - uv[6]) < 1e-5 &&
                        Math.Abs(uv[5] - uv[7]) < 1e-5 &&
                        uv[0] >= -1e-5 && uv[2] <= 1.00001 &&
                        uv[0] <= uv[2] && uv[1] >= -1e-5 &&
                        uv[5] <= 1.00001 && uv[1] <= uv[5];
            result.Add(new TexinfoRecord(i, name, layer, uv, tail,
                rect ? "RECT_OK" : "NONRECT_OR_OUT_OF_RANGE"));
        }
        return result;
    }
}
