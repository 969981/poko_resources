using Edoke.IO;
using System.Buffers.Binary;

namespace Pokopia.Binary;

/// <summary>
/// Raw 4-byte-aligned KIDSOBJDB observation only; NOT an inferred object table schema.
/// Matches the Python audit: p=object, p+0x30=G1T, p+0x34=TEXINFO.
/// </summary>
public sealed record NativeHashTriple(long Offset, uint ObjectHash, uint G1tHash, uint TexinfoHash);

public static class NativeHashTriples
{
    public static NativeHashTriple ReadAt(Stream stream, long offset)
    {
        if (!stream.CanSeek || offset < 0 || offset > stream.Length - 0x38)
            throw new InvalidDataException("HASH_TRIPLE_OFFSET_OUT_OF_RANGE");
        using var reader = new BinaryStreamReader(stream, bigEndian: false, leaveOpen: true);
        reader.Seek(offset);
        uint objectHash = reader.ReadUInt32();
        reader.Seek(offset + 0x30);
        uint g1t = reader.ReadUInt32();
        uint texinfo = reader.ReadUInt32();
        return new NativeHashTriple(offset, objectHash, g1t, texinfo);
    }

    /// <summary>Bounded 1-MiB scan with 0x37-byte overlap; no whole-file allocations.</summary>
    public static long? Find(Stream stream, uint objectHash, uint g1tHash, uint texinfoHash)
    {
        if (!stream.CanSeek || !stream.CanRead) throw new ArgumentException("Seekable readable stream required");
        const int chunk = 1024 * 1024;
        byte[] buffer = new byte[chunk + 0x37];
        for (long start = 0; start <= stream.Length - 0x38; start += chunk)
        {
            int bytes = (int)Math.Min(buffer.Length, stream.Length - start);
            stream.Position = start;
            stream.ReadExactly(buffer.AsSpan(0, bytes));
            int candidateBytes = (int)Math.Min(chunk, stream.Length - start - 0x37);
            for (int i = 0; i < candidateBytes; i += 4)
            {
                if (BinaryPrimitives.ReadUInt32LittleEndian(buffer.AsSpan(i, 4)) != objectHash)
                    continue;
                var reader = new BinarySpanReader(buffer.AsSpan(i, 0x38), bigEndian: false);
                uint obj = reader.ReadUInt32();
                reader.Seek(0x30);
                if (reader.ReadUInt32() == g1tHash && reader.ReadUInt32() == texinfoHash)
                    return start + i;
            }
        }
        return null;
    }
}
