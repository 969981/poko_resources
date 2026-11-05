using Edoke.IO;
using System.Text;

namespace Pokopia.Binary;

/// <summary>Exact eight-byte root/system RDX record (matches Scripts/unpack/core.py).</summary>
public sealed record RdxRecord(int Position, ushort FdataIndex, ushort PlatformFlags, uint FdataHash)
{
    public string FdataFilename => $"0x{FdataHash:x8}.fdata";
}

public static class RdxReader
{
    public static IEnumerable<RdxRecord> Read(Stream stream)
    {
        if (!stream.CanSeek || stream.Length % 8 != 0)
            throw new InvalidDataException("RDX_SIZE_NOT_MULTIPLE_OF_8");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(0);
        for (long i = 0, count = stream.Length / 8; i < count; i++)
        {
            if (i > int.MaxValue) throw new InvalidDataException("RDX_TOO_MANY_RECORDS");
            yield return new RdxRecord((int)i, reader.ReadUInt16(), reader.ReadUInt16(), reader.ReadUInt32());
        }
    }
}

/// <summary>Byte-preserving RDB record; unknown footer formats remain explicitly opaque.</summary>
public sealed record RdbRecord(
    int RecordIndex, long Offset, ulong EntrySize, ulong UncompressedSize,
    uint EntryType, uint NameHash, uint TypeHash, uint Flags, ushort FooterMagic,
    uint FdataOffset, uint FdataEntrySize, int FdataIndex, byte FooterTail,
    string FooterLayout, string FooterRawHex);

public static class RdbReader
{
    public static IEnumerable<RdbRecord> Read(Stream stream, int rdxCount)
    {
        if (!stream.CanSeek || stream.Length < 32 || rdxCount < 0)
            throw new InvalidDataException("RDB_BAD_HEADER_OR_RDX_COUNT");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(0);
        if (Encoding.ASCII.GetString(reader.ReadBytes(8)) != "_DRK0000")
            throw new InvalidDataException("RDB_BAD_HEADER");
        uint headerSize = reader.ReadUInt32();
        _ = reader.ReadUInt32();  // Reserved header field
        uint advertisedCount = reader.ReadUInt32();
        _ = reader.ReadUInt32();  // Header hash
        if (headerSize != 32) throw new InvalidDataException("RDB_UNKNOWN_HEADER_SIZE");
        long at = headerSize;
        int parsed = 0;
        while (at < stream.Length)
        {
            if (stream.Length - at < 48)
                throw new InvalidDataException($"RDB_BAD_RECORD_HEADER:{at}");
            reader.Seek(at);
            if (Encoding.ASCII.GetString(reader.ReadBytes(8)) != "IDRK0000")
                throw new InvalidDataException($"RDB_BAD_RECORD_MAGIC:{at}");
            ulong entrySize = reader.ReadUInt64();
            ulong footerSize = reader.ReadUInt64();
            ulong unpacked = reader.ReadUInt64();
            uint entryType = reader.ReadUInt32();
            uint nameHash = reader.ReadUInt32();
            uint typeHash = reader.ReadUInt32();
            uint flags = reader.ReadUInt32();
            if (footerSize < 13 || footerSize > 128 ||
                entrySize < 48 + footerSize || entrySize > (ulong)(stream.Length - at))
                throw new InvalidDataException($"RDB_BAD_ENTRY_SIZE_OR_FOOTER:{at}");
            reader.Seek(checked(at + (long)(entrySize - footerSize)));
            byte[] footer = reader.ReadBytes((int)footerSize);
            if (footer.Length != (int)footerSize) throw new EndOfStreamException("RDB_TRUNCATED_FOOTER");
            var f = new BinaryMemoryReader(footer, bigEndian: false);
            ushort magic = f.ReadUInt16();
            uint fdataOffset = 0, fdataSize = 0;
            int index = -1;
            byte tail = 0;
            string layout = $"opaque_{footerSize}";
            if (footerSize == 13)
            {
                fdataOffset = f.ReadUInt32();
                fdataSize = f.ReadUInt32();
                index = f.ReadUInt16();
                tail = f.ReadByte();
                if (index >= rdxCount)
                    throw new InvalidDataException($"RDB_INVALID_RDX_POSITION:{at}:{index}");
                layout = "standard_13";
            }
            else if (footerSize == 17)
            {
                uint marker = f.ReadUInt32();
                uint candidateOffset = f.ReadUInt32();
                uint candidateSize = f.ReadUInt32();
                int candidateIndex = f.ReadUInt16();
                byte candidateTail = f.ReadByte();
                if (magic == 0x0401 && marker == 0x80000000 &&
                    candidateIndex < rdxCount && candidateOffset % 16 == 0 &&
                    candidateSize >= 48 && candidateTail == 0)
                {
                    fdataOffset = candidateOffset;
                    fdataSize = candidateSize;
                    index = candidateIndex;
                    tail = candidateTail;
                    layout = "extended_17";
                }
                else layout = "opaque_17";
            }
            if (parsed == int.MaxValue) throw new InvalidDataException("RDB_TOO_MANY_RECORDS");
            yield return new RdbRecord(parsed++, at, entrySize, unpacked,
                entryType, nameHash, typeHash, flags, magic, fdataOffset,
                fdataSize, index, tail, layout, Convert.ToHexString(footer).ToLowerInvariant());
            long aligned = checked((long)((entrySize + 3UL) & ~3UL));
            if (aligned <= 0 || aligned > stream.Length - at)
                throw new InvalidDataException("RDB_ALIGNED_RECORD_OVERRUN");
            at += aligned;
        }
        if ((uint)parsed != advertisedCount || at != stream.Length)
            throw new InvalidDataException($"RDB_COUNT_OR_END_MISMATCH:{parsed}:{advertisedCount}:{at}:{stream.Length}");
    }
}
