Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::OpenRead('dist\universal_ai_gis_studio-1.0.0.zip')
$Entries = $Zip.Entries

$PluginName = "universal_ai_gis_studio"

$Req = "$PluginName/metadata.txt"
Write-Host "Looking for: $Req"

foreach ($Entry in $Entries) {
    $EntryPath = [string]$Entry.FullName -replace '\\', '/'
    Write-Host "  Entry: '$EntryPath' - Match: $($EntryPath -eq $Req)"
}

$Zip.Dispose()