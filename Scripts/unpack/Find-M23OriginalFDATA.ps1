# Pokopia 2.0.1 M23: local read-only scan for unarchived FF03 FDATA.
# Works on Windows PowerShell 5.1 and PowerShell 7. Does not copy, extract,
# rename, modify or upload copyrighted ROMFS source containers.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
    [string] $Root,
    [string] $OutputCsv = ".\m23_ff03_original_fdata_inventory.csv",
    [switch] $IncludeSHA256
)
$ErrorActionPreference = "Stop"
$Names = @(
    "0x03a38715.fdata",
    "0xfd6af828.fdata"
)
$StartPath = (Resolve-Path -LiteralPath $Root).ProviderPath.TrimEnd('\', '/')
$Findings = New-Object 'System.Collections.Generic.List[object]'
$Files = Get-ChildItem -LiteralPath $StartPath -File -Recurse -ErrorAction Stop
foreach ($File in $Files) {
    foreach ($Target in $Names) {
        if ($File.Name -ieq $Target) {
            $Kind = "DIRECT_FDATA"
            $Part = 0
        } elseif ($File.Name -match ('(?i)^' + [regex]::Escape($Target) + '\.7z\.(\d{3,})$')) {
            $Kind = "7Z_VOLUME"
            $Part = [int]$Matches[1]
        } else {
            continue
        }
        $Relative = $File.FullName.Substring($StartPath.Length).TrimStart('\','/')
        $Hash = ""
        if ($IncludeSHA256) { $Hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
        $Findings.Add([pscustomobject]@{
            TargetContainer = $Target
            RdxPlatformRaw = "FF03"
            RootScanned = $StartPath
            RelativePath = $Relative
            FullPath = $File.FullName
            ParentDirectory = $File.DirectoryName
            FileSizeBytes = $File.Length
            Representation = $Kind
            VolumeNumber = $Part
            SHA256 = $Hash
            Status = "LOCATED_NOT_IDRK_VERIFIED"
        })
    }
}
foreach ($Target in $Names) {
    $TargetRows = @($Findings | Where-Object { $_.TargetContainer -ieq $Target })
    if ($TargetRows.Count -eq 0) {
        $Findings.Add([pscustomobject]@{
            TargetContainer=$Target; RdxPlatformRaw="FF03"; RootScanned=$StartPath
            RelativePath=""; FullPath=""; ParentDirectory=""; FileSizeBytes=0
            Representation=""; VolumeNumber=0; SHA256=""
            Status="NOT_FOUND_IN_SELECTED_ROOT"
        })
        continue
    }
    $ByFolder = $TargetRows | Where-Object { $_.Representation -eq "7Z_VOLUME" } |
        Group-Object -Property ParentDirectory
    foreach ($Group in $ByFolder) {
        $Numbers = @($Group.Group | ForEach-Object { $_.VolumeNumber } | Sort-Object -Unique)
        $Last = ($Numbers | Measure-Object -Maximum).Maximum
        if (-not ($Numbers.Count -eq $Last -and $Numbers[0] -eq 1)) {
            Write-Warning ("Archive split volume numbering is incomplete: " + $Target +
                " in " + $Group.Name + " [found: " + ($Numbers -join ',') + "]")
        }
    }
}
$Parent = Split-Path -Parent $OutputCsv
if ($Parent -and -not (Test-Path -LiteralPath $Parent)) {
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
}
$Findings | Sort-Object TargetContainer,ParentDirectory,VolumeNumber |
    Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8
$Findings | Select-Object TargetContainer,Representation,RelativePath,Status |
    Format-Table -AutoSize
Write-Host ("M23 local inventory written: " + (Resolve-Path -LiteralPath $OutputCsv).ProviderPath)
Write-Host "No input bytes were extracted or uploaded. The FF03 flag's platform identity remains unverified."
