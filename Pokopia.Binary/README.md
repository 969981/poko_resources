# Pokopia.Binary — .NET 10 read-only native index inspection

This is an **additive** parser within the 2.0.1_unpack branch. It does not
replace, modify, or invoke the existing Python unpack/decompression/PNG/CSV/SQLite
evidence pipeline under Scripts/ and UnPack/.

## Dependencies and build

- .NET SDK 10.0.x
- The external Edoke C# reader library (MIT), pinned to a reviewed Git commit
  using a Git submodule at ThirdParty/Edoke
- Edoke itself targets net8.0; net10.0 can reference that library

Clone with: git clone --recurse-submodules -b 2.0.1_unpack https://github.com/969981/poko_resources.git

For an existing checkout: git submodule update --init --recursive ThirdParty/Edoke

Build / check from repository root:

    dotnet build Pokopia.Binary/Pokopia.Binary.csproj -c Release
    dotnet build Pokopia.Binary.Cli/Pokopia.Binary.Cli.csproj -c Release
    dotnet run --project Pokopia.Binary.Checks -c Release

The separate CI workflow checks one **actual** 2.0.1 TEXINFO atlas
(root_042753_b4b1fe49.texinfo): 138636 bytes, 1333 records, 727 layer 0,
606 layer 1, and cross-checks all raw names/layers/UVs with Python struct.
Only the CI test input is read. It never exports or commits game bytes.

## Read-only CLI

The CLI writes JSON lines to stdout (easy to consume with Python / jq).
Offset arguments are decimal or 0x-prefixed hex; Hash arguments are hex.

    dotnet run --project Pokopia.Binary.Cli -- rdx PATH_TO_ROOT.RDX
    dotnet run --project Pokopia.Binary.Cli -- rdb PATH_TO_ROOT.RDB RDX_RECORD_COUNT
    dotnet run --project Pokopia.Binary.Cli -- idrk PATH_TO_FDATA 0xOFFSET
    dotnet run --project Pokopia.Binary.Cli -- kids PATH_TO_KIDSOBJDB
    dotnet run --project Pokopia.Binary.Cli -- texinfo PATH_TO_TEXINFO
    dotnet run --project Pokopia.Binary.Cli -- triple PATH_TO_KIDSOBJDB 315040
    dotnet run --project Pokopia.Binary.Cli -- find-triple PATH_TO_KIDSOBJDB 9a25ce0c d09a60bd 048fc972

The triple example is a previously verified **raw U32 observation**;
matching three words does not by itself assign full object semantics.

## Provenance and scope

Existing reference implementations are the current Python files:
- Scripts/unpack/core.py: RDX 8-byte entries, RDB header and 13/17-byte
  footer, IDRK 48-byte record header; keep unknown footer types opaque
- Scripts/unpack/decode_kidsobjdb.py: _DOK0000, IDOK/RDOK, fixed-width
  property metadata; unknown property types or RDOK meanings remain partial
- Scripts/resources/g1t_to_png.py: TEXINFO 4 + count * 104 byte atlas records
- Scripts/resources/trace_item_textures.py: raw hash triples at p,
  p+0x30 and p+0x34 on four-byte-aligned candidate offsets

Status levels remain distinct: raw index parse != physical resource presence
!= decompression != correct G1T image/UV != proven game object or text ID.

The following are deliberately NOT implemented by this .NET project:
Oodle, KT-zlib, G1T swizzle/BC7/BC3, PNG, complete KIDSOBJDB semantics,
nine-language localization ID recovery, source asset copying, and writeback.
Existing Python remains authoritative until an explicit parity-tested migration.

## Large file behavior and safety

RDB and RDX are read one record at a time from a seekable stream. IDRK
inspects header/metadata without loading FDATA. The hash-triple scan reads
bounded 1-MiB chunks plus 55 bytes overlap; it never opens huge files as
one byte array. KIDSOBJDB structurally traverses all blocks, but only stores
a bounded summary (default first 32 blocks and 32 properties each).
The TEXINFO reader intentionally materializes at most 65536 small records.
No parser writes to an input file.

Edoke's native SubStream is not used here because its boundary and
end-of-stream behavior needs additional hardening for hostile offsets.
