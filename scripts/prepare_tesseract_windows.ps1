$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Manifest = Get-Content (Join-Path $Root "packaging\tesseract_manifest.json") -Raw | ConvertFrom-Json
$TesseractVersion = $Manifest.windows_binary.version
$TesseractPackage = $Manifest.windows_binary.package_id
$TessdataTag = $Manifest.traineddata.git_ref
$Stage = Join-Path $Root "build\vendor\tesseract"
$WorkTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$TempData = Join-Path $WorkTemp "dca-tessdata-fast"
$TempSource = Join-Path $WorkTemp "dca-tesseract-source"

Write-Host "Preparing pinned Tesseract $TesseractVersion"
Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item $Stage -ItemType Directory -Force | Out-Null

# Chocolatey verifies the fixed package version and its upstream installer
# checksum. --require-checksums makes a missing package checksum fatal.
choco install $TesseractPackage --version=$TesseractVersion --yes --no-progress --require-checksums --force --allow-downgrade
$Installed = Join-Path $env:ProgramFiles "Tesseract-OCR"
if (-not (Test-Path (Join-Path $Installed "tesseract.exe"))) {
  throw "Pinned Tesseract installation was not found at $Installed"
}
Copy-Item (Join-Path $Installed "*") $Stage -Recurse -Force

# Language data is fetched only during release building from an immutable tag.
Remove-Item $TempData -Recurse -Force -ErrorAction SilentlyContinue
git clone --depth 1 --branch $TessdataTag $Manifest.traineddata.repository $TempData
New-Item (Join-Path $Stage "tessdata") -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $TempData "eng.traineddata") (Join-Path $Stage "tessdata\eng.traineddata") -Force
Copy-Item (Join-Path $TempData "kor.traineddata") (Join-Path $Stage "tessdata\kor.traineddata") -Force
New-Item (Join-Path $Stage "licenses") -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $TempData "LICENSE") (Join-Path $Stage "licenses\tessdata.txt") -Force
Remove-Item $TempSource -Recurse -Force -ErrorAction SilentlyContinue
git clone --depth 1 --branch $Manifest.license_source.git_ref $Manifest.license_source.repository $TempSource
Copy-Item (Join-Path $TempSource "LICENSE") (Join-Path $Stage "licenses\tesseract.txt") -Force

$Required = @("tesseract.exe", "tessdata\eng.traineddata", "tessdata\kor.traineddata", "licenses\tesseract.txt", "licenses\tessdata.txt")
foreach ($Item in $Required) {
  if (-not (Test-Path (Join-Path $Stage $Item))) { throw "Missing bundled OCR file: $Item" }
}
if (-not (Get-ChildItem $Stage -Filter "*.dll")) { throw "Tesseract runtime DLLs were not staged" }
Get-FileHash (Join-Path $Stage "tesseract.exe"), (Join-Path $Stage "tessdata\eng.traineddata"), (Join-Path $Stage "tessdata\kor.traineddata") -Algorithm SHA256 |
  Format-Table Path, Hash
Write-Host "Bundled OCR ready: $Stage"
