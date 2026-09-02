<#
.SYNOPSIS
    Packages the PyInstaller output into a signed MSIX.

.DESCRIPTION
    1. Generates MSIX visual assets (PNGs) from the app icon.
    2. Patches AppxManifest.xml with the correct version and publisher.
    3. Copies PyInstaller dist + manifest + assets into a staging folder.
    4. Runs MakeAppx.exe to create the .msix.
    5. Signs the .msix with a local PFX certificate or Azure Trusted
         Signing DLib. CI uses -SkipSign and retains the package as a
         short-lived artifact for Publish-SignedMsix.ps1.

.PARAMETER Version
    Semantic version (e.g. "0.5.0"). A ".0" build number is appended
    automatically to satisfy MSIX's four-part requirement.

.PARAMETER Publisher
    The certificate subject (CN=...) that matches your signing
    certificate.  Defaults to the placeholder in the manifest.

.PARAMETER SkipSign
    If set, skips the signing step (useful for local testing).

.PARAMETER LocalPfx
    Path to a local .pfx certificate file for signing.  When provided,
    signs with SignTool using this certificate instead of Azure Trusted
    Signing.  Use with -PfxPassword if the certificate is password-protected.

.PARAMETER PfxPassword
    Password for the local .pfx certificate (optional).

.PARAMETER AzureEndpoint
    Azure Trusted Signing endpoint URL (local Azure signing).

.PARAMETER AzureCodeSigningAccountName
    Azure Trusted Signing account name (local Azure signing).

.PARAMETER AzureCertificateProfileName
    Azure Trusted Signing certificate profile name (local Azure signing).

.PARAMETER DlibPath
    Path to Azure.CodeSigning.Dlib.dll.  When omitted, the script
    searches the default NuGet package cache automatically.

.EXAMPLE
    # Unsigned MSIX (local testing / sideloading)
    .\Build-Msix.ps1 -Version "0.5.0" -SkipSign

.EXAMPLE
    # Sign with a local PFX certificate
    .\Build-Msix.ps1 -Version "0.5.0" -LocalPfx ".\cert.pfx" -PfxPassword "secret" -Publisher "CN=MyName"

.EXAMPLE
    # Sign with Azure Trusted Signing (local)
    .\Build-Msix.ps1 -Version "0.5.0" -Publisher "CN=..." -AzureEndpoint "https://eus.codesigning.azure.net/" -AzureCodeSigningAccountName "myacct" -AzureCertificateProfileName "myprofile"
#>

param(
    [Parameter(Mandatory)]
    [string]$Version,

    [string]$Publisher = "",

    [switch]$SkipSign,

    # Local signing
    [string]$LocalPfx = "",
    [string]$PfxPassword = "",

    # Azure Trusted Signing parameters (local signing only)
    [string]$AzureEndpoint = "",
    [string]$AzureCodeSigningAccountName = "",
    [string]$AzureCertificateProfileName = "",

    # Path to Azure.CodeSigning.Dlib.dll (optional; auto-detected from NuGet cache if omitted)
    [string]$DlibPath = ""
)

$ErrorActionPreference = "Stop"
$FollowCursorRoot = Split-Path -Parent $PSScriptRoot   # followcursor/
$DistDir = Join-Path $FollowCursorRoot "dist\FollowCursor"
$MsixDir = Join-Path $FollowCursorRoot "msix"
$StagingDir = Join-Path $FollowCursorRoot "dist\msix_staging"
$OutputMsix = Join-Path $FollowCursorRoot "dist\FollowCursor-$Version.msix"

# ── Validate prerequisites ──────────────────────────────────────
if (-not (Test-Path $DistDir)) {
    Write-Error "PyInstaller output not found at $DistDir. Run Build-App.ps1 first."
}
if (-not (Test-Path (Join-Path $MsixDir "AppxManifest.xml"))) {
    Write-Error "AppxManifest.xml not found in $MsixDir."
}

# ── 1. Generate MSIX visual assets ──────────────────────────────
Write-Host "Generating MSIX visual assets..." -ForegroundColor Cyan
$python = Join-Path $FollowCursorRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}
& $python (Join-Path $FollowCursorRoot "generate_msix_assets.py")
if ($LASTEXITCODE -ne 0) { Write-Error "Asset generation failed." }

# ── 2. Patch manifest with version + publisher ──────────────────
Write-Host "Patching AppxManifest.xml..." -ForegroundColor Cyan
$manifest = Get-Content (Join-Path $MsixDir "AppxManifest.xml") -Raw

# MSIX requires four-part version: Major.Minor.Patch.Build
$msixVersion = "$Version.0"
# Only replace Version in the <Identity> element, not the XML declaration
$manifest = $manifest -replace '(<Identity[^>]*?)Version="[^"]*"', "`$1Version=`"$msixVersion`""

if ($Publisher) {
    $manifest = $manifest -replace '(<Identity[^>]*?)Publisher="[^"]*"', "`$1Publisher=`"$Publisher`""
}

# Write patched manifest to staging (don't modify the template)
if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null

# ── 3. Stage files ──────────────────────────────────────────────
Write-Host "Staging MSIX content..." -ForegroundColor Cyan

# Preserve the PyInstaller onedir layout. FollowCursor.exe resolves its runtime
# DLLs relative to the _internal directory.
$pythonRuntime = Get-ChildItem (Join-Path $DistDir "_internal\python[0-9][0-9][0-9].dll") -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $pythonRuntime) {
    Write-Error "PyInstaller Python runtime DLL not found under $DistDir\_internal."
}
Copy-Item "$DistDir\*" $StagingDir -Recurse -Force
$stagedPythonRuntime = Join-Path $StagingDir "_internal\$($pythonRuntime.Name)"
if (-not (Test-Path $stagedPythonRuntime -PathType Leaf)) {
    Write-Error "MSIX staging lost the PyInstaller runtime DLL: $stagedPythonRuntime"
}

# Copy assets
$assetsStaging = Join-Path $StagingDir "Assets"
New-Item -ItemType Directory -Path $assetsStaging -Force | Out-Null
Copy-Item (Join-Path $MsixDir "Assets\*") $assetsStaging -Recurse -Force

# Write patched manifest (UTF-8 without BOM — MakeAppx rejects BOM)
$manifestPath = Join-Path $StagingDir "AppxManifest.xml"
[System.IO.File]::WriteAllText($manifestPath, $manifest, [System.Text.UTF8Encoding]::new($false))

# ── 4. Build MSIX ───────────────────────────────────────────────
Write-Host "Building MSIX package..." -ForegroundColor Cyan

$sdkBinPaths = @(
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\MakeAppx.exe"
    "${env:ProgramFiles}\Windows Kits\10\bin\*\x64\MakeAppx.exe"
)
$makeAppx = $sdkBinPaths | ForEach-Object { Resolve-Path $_ -ErrorAction SilentlyContinue } |
    Sort-Object -Descending | Select-Object -First 1

if (-not $makeAppx) {
    Write-Error "MakeAppx.exe not found. Install the Windows SDK (Desktop C++ workload)."
}

& $makeAppx.Path pack /d $StagingDir /p $OutputMsix /o
if ($LASTEXITCODE -ne 0) { Write-Error "MakeAppx.exe failed." }

Write-Host "MSIX created: $OutputMsix" -ForegroundColor Green

# ── 5. Sign ─────────────────────────────────────────────────────
if ($SkipSign) {
    Write-Host "Signing skipped (-SkipSign)." -ForegroundColor Yellow
    return
}

# Find SignTool.exe (shared by both local and Azure signing)
$signToolPaths = @(
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe"
    "${env:ProgramFiles}\Windows Kits\10\bin\*\x64\signtool.exe"
)
$signTool = $signToolPaths | ForEach-Object { Resolve-Path $_ -ErrorAction SilentlyContinue } |
    Sort-Object -Descending | Select-Object -First 1

if (-not $signTool) {
    Write-Error "SignTool.exe not found. Install the Windows SDK."
}

# ── 5a. Local PFX signing ───────────────────────────────────────
if ($LocalPfx) {
    $LocalPfx = $LocalPfx.Trim('"', "'", ' ')
    if (-not (Test-Path $LocalPfx)) {
        Write-Error "PFX file not found: $LocalPfx"
    }
    Write-Host "Signing with local certificate: $LocalPfx" -ForegroundColor Cyan

    $signArgs = @("sign", "/v", "/fd", "SHA256", "/f", $LocalPfx)
    if ($PfxPassword) {
        $signArgs += "/p"
        $signArgs += $PfxPassword
    }
    $signArgs += "/tr"
    $signArgs += "http://timestamp.digicert.com"
    $signArgs += "/td"
    $signArgs += "SHA256"
    $signArgs += $OutputMsix

    & $signTool.Path @signArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "Local signing failed." }

    Write-Host "MSIX signed successfully (local PFX): $OutputMsix" -ForegroundColor Green
    return
}

# ── 5b. Azure Trusted Signing ───────────────────────────────────
if (-not $AzureEndpoint -or -not $AzureCodeSigningAccountName -or -not $AzureCertificateProfileName) {
    Write-Host "No signing method specified. Use -LocalPfx or Azure Trusted Signing parameters." -ForegroundColor Yellow
    return
}

Write-Host "Signing with Azure Trusted Signing..." -ForegroundColor Cyan

if ($DlibPath) {
    if (-not (Test-Path -Path $DlibPath -PathType Leaf)) {
        Write-Error "Specified DLib file not found (or is not a file): $DlibPath"
    }
    $dlibFile = Get-Item $DlibPath
    if ($dlibFile.Name -ne "Azure.CodeSigning.Dlib.dll") {
        Write-Error "Invalid DLib file name '$($dlibFile.Name)'. Expected 'Azure.CodeSigning.Dlib.dll'."
    }
} else {
    # Auto-detect from NuGet package cache
    $searchPaths = @(
        "$env:USERPROFILE\.nuget\packages\microsoft.trusted.signing.client"
    )
    $dlibFile = $searchPaths | Where-Object { Test-Path $_ } |
        ForEach-Object { Get-ChildItem -Path $_ -Filter "Azure.CodeSigning.Dlib.dll" -Recurse -ErrorAction SilentlyContinue } |
        Where-Object { $_.FullName -match "x64" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1

    if (-not $dlibFile) {
        Write-Error "Azure.CodeSigning.Dlib.dll not found. Pass -DlibPath with the full path to Azure.CodeSigning.Dlib.dll (for example from an existing NuGet cache or CI environment)."
    }
}

$metadataJson = @{
    Endpoint               = $AzureEndpoint
    CodeSigningAccountName = $AzureCodeSigningAccountName
    CertificateProfileName = $AzureCertificateProfileName
} | ConvertTo-Json

$metadataPath = Join-Path $env:TEMP "trustedsigning-metadata.json"
$metadataJson | Set-Content $metadataPath -Encoding UTF8

& $signTool.Path sign /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 /dlib $dlibFile.FullName /dmdf $metadataPath $OutputMsix

if ($LASTEXITCODE -ne 0) { Write-Error "Signing failed." }

Write-Host "MSIX signed successfully (Azure Trusted Signing): $OutputMsix" -ForegroundColor Green
Remove-Item $metadataPath -ErrorAction SilentlyContinue
