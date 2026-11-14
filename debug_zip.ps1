Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::OpenRead('dist\universal_ai_gis_studio-1.0.0.zip')
$Entries = $Zip.Entries
foreach ($Entry in $Entries) {
    Write-Host "Entry: '$($Entry.FullName)'"
}
$Zip.Dispose()