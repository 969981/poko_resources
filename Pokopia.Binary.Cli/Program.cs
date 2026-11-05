using Pokopia.Binary;
using System.Globalization;
using System.Text.Json;

static long Offset(string text) => text.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
    ? long.Parse(text.AsSpan(2), NumberStyles.HexNumber, CultureInfo.InvariantCulture)
    : long.Parse(text, CultureInfo.InvariantCulture);

static uint Hash(string text) => uint.Parse(text.AsSpan(
    text.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? 2 : 0),
    NumberStyles.HexNumber, CultureInfo.InvariantCulture);

static void Print(object value) => Console.WriteLine(JsonSerializer.Serialize(value));

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: dotnet run --project Pokopia.Binary.Cli -- [rdx|rdb|idrk|kids|texinfo|triple|find-triple] FILE [args]");
    Console.Error.WriteLine("rdb needs RDX_RECORD_COUNT; idrk/triple need OFFSET; find-triple needs OBJECT_HASH G1T_HASH TEXINFO_HASH (hex).");
    return 2;
}

try
{
    using var input = File.OpenRead(args[1]);
    switch (args[0].ToLowerInvariant())
    {
        case "rdx":
            foreach (var row in RdxReader.Read(input)) Print(row);
            break;
        case "rdb":
            if (args.Length < 3) throw new ArgumentException("rdb needs RDX record count");
            foreach (var row in RdbReader.Read(input, int.Parse(args[2], CultureInfo.InvariantCulture)))
                Print(row);
            break;
        case "idrk":
            if (args.Length < 3) throw new ArgumentException("idrk needs offset");
            Print(IdrkReader.Read(input, Offset(args[2])));
            break;
        case "kids":
            Print(KidsObjDbReader.Inspect(input));
            break;
        case "texinfo":
            foreach (var row in TexinfoReader.Read(input)) Print(row);
            break;
        case "triple":
            if (args.Length < 3) throw new ArgumentException("triple needs offset");
            Print(NativeHashTriples.ReadAt(input, Offset(args[2])));
            break;
        case "find-triple":
            if (args.Length < 5) throw new ArgumentException("find-triple needs 3 hashes");
            long? found = NativeHashTriples.Find(input, Hash(args[2]), Hash(args[3]), Hash(args[4]));
            Print(new { status = found.HasValue ? "MATCHED_RAW_U32_TRIPLE" : "NOT_FOUND",
                offset = found, semanticIdentity = "UNPROVEN" });
            break;
        default:
            throw new ArgumentException($"Unknown command: {args[0]}");
    }
    return 0;
}
catch (Exception ex) when (ex is IOException or ArgumentException or FormatException or OverflowException)
{
    Console.Error.WriteLine($"{ex.GetType().Name}: {ex.Message}");
    return 1;
}
