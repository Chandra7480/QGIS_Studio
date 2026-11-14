Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::OpenRead('dist\universal_ai_gis_studio-1.0.0.zip')
$Entries = $Zip.Entries

$PluginName = "universal_ai_gis_studio"

$RequiredInZip = @(
    "$PluginName/metadata.txt",
    "$PluginName/__init__.py",
    "$PluginName/plugin.py",
    "$PluginName/resources/icon.png",
    "$PluginName/about.html"
)

foreach ($Req in $RequiredInZip) {
    Write-Host "`nLooking for: $Req"
    $Found = $false
    foreach ($Entry in $Entries) {
        $EntryPath = [string]$Entry.FullName -replace '\\', '/'
        if ($EntryPath -eq $Req) {
            Write-Host "  FOUND: $EntryPath"
            $Found = $true
            break
        }
    }
    if (-not $Found) {
        Write-Host "  NOT FOUND!"
    }
}

$Zip.Dispose()