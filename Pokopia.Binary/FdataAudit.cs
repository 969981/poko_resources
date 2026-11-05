namespace Pokopia.Binary;

/// <summary>
/// Index-to-container audit. VERIFIED_IDRK_HEADER proves framing and four
/// header fields only; it does NOT prove decompressed payload or resource identity.
/// </summary>
public sealed record FdataAuditRow(
    int RecordIndex, int FdataIndex, string? FdataFilename,
    string? PhysicalPath, long? Offset, string Status, string Detail,
    uint RdbNameHash, uint RdbTypeHash, ulong RdbUnpackedSize,
    ulong RdbFdataEntrySize);

public static class FdataAuditor
{
    private sealed class BoundedFileCache : IDisposable
    {
        private const int MaxOpen = 8;
        private readonly Dictionary<string, FileStream> _files = new(StringComparer.Ordinal);
        private readonly Queue<string> _order = new();

        public FileStream Open(string path)
        {
            if (_files.TryGetValue(path, out var existing))
                return existing;
            if (_order.Count >= MaxOpen)
            {
                string old = _order.Dequeue();
                _files.Remove(old, out var stream);
                stream?.Dispose();
            }
            var opened = File.OpenRead(path);
            _files.Add(path, opened);
            _order.Enqueue(path);
            return opened;
        }

        public void Dispose()
        {
            foreach (var stream in _files.Values) stream.Dispose();
            _files.Clear();
            _order.Clear();
        }
    }

    /// <summary>Same platform-first lookup rules as Scripts/unpack/core.py.</summary>
    private static (string? Path, string Status) Locate(string root, RdxRecord rdx)
    {
        string name = rdx.FdataFilename;
        string basePath = Path.Combine(root, name);
        string mount1 = Path.Combine(root, "MountPoint_1", name);
        string mount2 = Path.Combine(root, "MountPoint_2", name);
        string? preferred = rdx.PlatformFlags switch
        {
            0xffff => basePath,
            0xff01 => mount1,
            0xff02 => mount2,
            _ => null
        };
        if (preferred is not null && File.Exists(preferred))
            return (preferred, "FOUND");
        var found = new[] { basePath, mount1, mount2 }.Where(File.Exists).ToArray();
        return found.Length switch
        {
            0 => (null, "FDATA_MISSING"),
            1 => (found[0], "FOUND"),
            _ => (null, "FDATA_AMBIGUOUS")
        };
    }

    private static FdataAuditRow Inspect(RdbRecord record, IReadOnlyList<RdxRecord> rdx,
        string root, BoundedFileCache cache)
    {
        FdataAuditRow Row(string status, string detail, string? filename = null,
            string? path = null, long? offset = null) =>
            new(record.RecordIndex, record.FdataIndex, filename, path, offset, status,
                detail, record.NameHash, record.TypeHash, record.UncompressedSize,
                record.FdataEntrySize);

        if (record.FooterLayout is not ("standard_13" or "extended_17") ||
            record.FdataIndex < 0 || record.FdataIndex >= rdx.Count)
            return Row("UNRESOLVED_RDB_FOOTER", record.FooterLayout);

        var entry = rdx[record.FdataIndex];
        var (path, locateStatus) = Locate(root, entry);
        if (path is null)
            return Row(locateStatus, $"RDX_POSITION={record.FdataIndex}", entry.FdataFilename);

        try
        {
            var stream = cache.Open(path);
            var header = IdrkReader.Read(stream, record.FdataOffset);
            bool matches = header.NameHash == record.NameHash &&
                header.TypeHash == record.TypeHash &&
                header.UnpackedSize == record.UncompressedSize &&
                header.EntrySize == record.FdataEntrySize;
            return Row(matches ? "VERIFIED_IDRK_HEADER" : "IDRK_HEADER_MISMATCH",
                matches ? "NAME_TYPE_UNPACKED_ENTRYSIZE_EQUAL" :
                    $"actual:name={header.NameHash:x8},type={header.TypeHash:x8},unpacked={header.UnpackedSize},entrySize={header.EntrySize}",
                entry.FdataFilename, path, record.FdataOffset);
        }
        catch (InvalidDataException ex)
        {
            return Row("IDRK_INVALID", ex.Message, entry.FdataFilename, path, record.FdataOffset);
        }
        catch (IOException ex)
        {
            return Row("FDATA_IO_ERROR", ex.Message, entry.FdataFilename, path, record.FdataOffset);
        }
        catch (UnauthorizedAccessException ex)
        {
            return Row("FDATA_IO_ERROR", ex.Message, entry.FdataFilename, path, record.FdataOffset);
        }
    }

    /// <summary>
    /// Record-by-record audit, streaming RDB and holding at most eight FDATA
    /// handles. It never decompresses or writes source data.
    /// </summary>
    public static IEnumerable<FdataAuditRow> Read(
        Stream rdbStream, Stream rdxStream, string fdataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fdataRoot);
        var rdx = RdxReader.Read(rdxStream).ToArray();
        using var cache = new BoundedFileCache();
        foreach (var row in RdbReader.Read(rdbStream, rdx.Length))
            yield return Inspect(row, rdx, fdataRoot, cache);
    }
}
