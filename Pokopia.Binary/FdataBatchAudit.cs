using System.Diagnostics;

namespace Pokopia.Binary;

/// <summary>Bounded summary for very large native RDB/RDX and partial FDATA checkouts.</summary>
public sealed record FdataBatchSummary(
    long RdbRecordsInspected,
    long VerifiedIdrkHeaders,
    long MissingOrAmbiguousFdataRecords,
    long InvalidOrMismatchedIdrkHeaders,
    long UnresolvedFooterRecords,
    int PhysicalFdataFilesHeaderVerified,
    IReadOnlyDictionary<string, long> StatusCounts,
    IReadOnlyList<FdataAuditRow> EvidenceSamples,
    long ElapsedMilliseconds,
    string EvidenceGrade);

public static class FdataBatchAuditor
{
    /// <summary>
    /// Reports all index rows without holding them in memory. The source is
    /// read-only; no decoded payload or game bytes are emitted.
    /// </summary>
    public static FdataBatchSummary Summarize(
        Stream rdb, Stream rdx, string fdataRoot, int maxSamples = 24)
    {
        if (maxSamples < 0 || maxSamples > 512)
            throw new ArgumentOutOfRangeException(nameof(maxSamples));

        var timer = Stopwatch.StartNew();
        var status = new SortedDictionary<string, long>(StringComparer.Ordinal);
        var samples = new List<FdataAuditRow>();
        var physicalFiles = new HashSet<string>(StringComparer.Ordinal);
        long rows = 0, verified = 0, unavailable = 0, bad = 0, unresolved = 0;

        foreach (var entry in FdataAuditor.Read(rdb, rdx, fdataRoot))
        {
            rows++;
            status.TryGetValue(entry.Status, out var count);
            status[entry.Status] = count + 1;
            switch (entry.Status)
            {
                case "VERIFIED_IDRK_HEADER":
                    verified++;
                    if (entry.PhysicalPath is not null) physicalFiles.Add(entry.PhysicalPath);
                    break;
                case "FDATA_MISSING":
                case "FDATA_AMBIGUOUS":
                case "FDATA_IO_ERROR":
                    unavailable++;
                    break;
                case "IDRK_INVALID":
                case "IDRK_HEADER_MISMATCH":
                    bad++;
                    break;
                default:
                    unresolved++;
                    break;
            }

            // Keep a small number of sample mismatches plus positive examples;
            // counts are always complete, irrespective of the sample cap.
            if (samples.Count < maxSamples &&
                (entry.Status != "FDATA_MISSING" || samples.Count < maxSamples / 2))
                samples.Add(entry);
        }
        timer.Stop();
        return new FdataBatchSummary(rows, verified, unavailable, bad, unresolved,
            physicalFiles.Count, status, samples, timer.ElapsedMilliseconds,
            "IDRK_HEADER_BYTES_ONLY_NO_DECOMPRESSION_OR_GAME_SEMANTICS");
    }
}
