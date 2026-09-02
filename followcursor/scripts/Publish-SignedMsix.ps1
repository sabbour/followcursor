<#
.SYNOPSIS
    Signs a successful tag build's MSIX locally and publishes it to GitHub.

.DESCRIPTION
    Downloads the short-lived unsigned MSIX artifact, signs it through Azure
    Trusted Signing with the locally authenticated Azure user, verifies the
    signature, publisher, and timestamp, then uploads it to the GitHub release.

.EXAMPLE
    pwsh -NoProfile -File .\scripts\Publish-SignedMsix.ps1 -Version 0.14.1
#>

#Requires -Version 7.0

param(
    [Parameter(Mandatory)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [string]$Repository = "sabbour/followcursor",
    [string]$AzureEndpoint = "https://eus.codesigning.azure.net/",
    [string]$AzureCodeSigningAccountName = "asabbour-codesigning",
    [string]$AzureCertificateProfileName = "followcursor-cert",
    [string]$ResourceGroupName = "rg-codesigning",
    [string]$NuGetSource = "https://packagefeedproxy.microsoft.io/nuget/v3/index.json",
    [string]$DlibPath = ""
)

$ErrorActionPreference = "Stop"
$tag = "v$Version"
$artifactName = "FollowCursor-$Version-msix-unsigned"
$msixName = "FollowCursor-$Version.msix"
$workDir = Join-Path $env:TEMP "followcursor-release-$Version"

function Find-WindowsSdkTool {
    param([Parameter(Mandatory)][string]$Name)

    $paths = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\$Name"
        "${env:ProgramFiles}\Windows Kits\10\bin\*\x64\$Name"
    )
    $tool = $paths | ForEach-Object { Resolve-Path $_ -ErrorAction SilentlyContinue } |
        Sort-Object -Descending | Select-Object -First 1
    if (-not $tool) { throw "$Name not found. Install the Windows SDK." }
    return $tool.Path
}

function Assert-Command {
    param([Parameter(Mandatory)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required but was not found on PATH."
    }
}

function Invoke-AzCommand {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$Description
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        & az @Arguments 1> $stdoutPath 2> $stderrPath
        $exitCode = $LASTEXITCODE
        $stdout = (Get-Content $stdoutPath -Raw) ?? ""
        $stderr = (Get-Content $stderrPath -Raw) ?? ""
    }
    finally {
        Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }

    if ($exitCode -ne 0) {
        throw "$Description failed: $($stderr.Trim())"
    }
    return $stdout.Trim()
}

Assert-Command "az"
Assert-Command "dotnet"
Assert-Command "gh"

az account show -o none
if ($LASTEXITCODE -ne 0) { throw "Azure CLI is not authenticated. Run 'az login'." }
gh auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated. Run 'gh auth login'." }

$run = gh run list --repo $Repository --workflow build.yml --limit 100 `
    --json databaseId,headBranch,status,conclusion,event | ConvertFrom-Json |
    Where-Object { $_.headBranch -eq $tag -and $_.event -eq "push" } |
    Select-Object -First 1
if (-not $run) { throw "No workflow run found for $tag." }
if ($run.status -ne "completed" -or $run.conclusion -ne "success") {
    throw "Workflow run $($run.databaseId) for $tag is not successful."
}

gh release view $tag --repo $Repository | Out-Null
if ($LASTEXITCODE -ne 0) { throw "GitHub release $tag does not exist." }

if (Test-Path $workDir) { Remove-Item $workDir -Recurse -Force }
New-Item -ItemType Directory -Path $workDir | Out-Null
gh run download $run.databaseId --repo $Repository --name $artifactName --dir $workDir
if ($LASTEXITCODE -ne 0) { throw "Could not download artifact $artifactName." }

$msixPath = Join-Path $workDir $msixName
if (-not (Test-Path $msixPath -PathType Leaf)) { throw "Artifact did not contain $msixName." }

if (-not $DlibPath) {
    $dlib = Get-ChildItem "$HOME\.nuget\packages\microsoft.trusted.signing.client" `
        -Filter "Azure.CodeSigning.Dlib.dll" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '[\\/]x64[\\/]' } |
        Sort-Object FullName -Descending | Select-Object -First 1

    if (-not $dlib) {
        $bootstrapDir = Join-Path $workDir "signing-client"
        dotnet new classlib --output $bootstrapDir --force | Out-Null
        dotnet add (Join-Path $bootstrapDir "signing-client.csproj") package `
            Microsoft.Trusted.Signing.Client --source $NuGetSource
        if ($LASTEXITCODE -ne 0) { throw "Trusted Signing client restore failed through $NuGetSource." }
        $dlib = Get-ChildItem "$HOME\.nuget\packages\microsoft.trusted.signing.client" `
            -Filter "Azure.CodeSigning.Dlib.dll" -Recurse |
            Where-Object { $_.FullName -match '[\\/]x64[\\/]' } |
            Sort-Object FullName -Descending | Select-Object -First 1
    }
    if (-not $dlib) { throw "Azure.CodeSigning.Dlib.dll was not found after package restore." }
    $DlibPath = $dlib.FullName
}
if (-not (Test-Path $DlibPath -PathType Leaf)) { throw "DLib not found: $DlibPath" }

$signingAccountId = Invoke-AzCommand -Description "Trusted Signing account lookup" -Arguments @(
    "resource", "show",
    "--resource-group", $ResourceGroupName,
    "--resource-type", "Microsoft.CodeSigning/codeSigningAccounts",
    "--name", $AzureCodeSigningAccountName,
    "--query", "id",
    "-o", "tsv"
)
if (-not $signingAccountId) { throw "Trusted Signing account lookup returned no resource ID." }
$profileId = "$signingAccountId/certificateProfiles/$AzureCertificateProfileName"
$profileJson = Invoke-AzCommand -Description "Certificate profile lookup" -Arguments @(
    "resource", "show",
    "--ids", $profileId,
    "--api-version", "2024-02-05-preview",
    "-o", "json"
)
$profile = $profileJson | ConvertFrom-Json
if ($profile.properties.profileType -ne "PublicTrust") { throw "Certificate profile is not PublicTrust." }
$expectedPublisher = $profile.properties.certificates[0].subjectName
if (-not $expectedPublisher) { throw "Certificate profile has no active certificate subject." }

$makeAppx = Find-WindowsSdkTool "MakeAppx.exe"
$unpackDir = Join-Path $workDir "unpacked"
& $makeAppx unpack /p $msixPath /d $unpackDir /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not inspect the MSIX manifest." }
[xml]$manifest = Get-Content (Join-Path $unpackDir "AppxManifest.xml") -Raw
$manifestPublisher = $manifest.Package.Identity.Publisher
if ($manifestPublisher -ne $expectedPublisher) {
    throw "Manifest publisher '$manifestPublisher' does not match Trusted Signing subject '$expectedPublisher'."
}

$metadataPath = Join-Path $workDir "trustedsigning-metadata.json"
@{
    Endpoint = $AzureEndpoint
    CodeSigningAccountName = $AzureCodeSigningAccountName
    CertificateProfileName = $AzureCertificateProfileName
} | ConvertTo-Json | Set-Content $metadataPath -Encoding utf8NoBOM

$signTool = Find-WindowsSdkTool "SignTool.exe"
& $signTool sign /v /fd SHA256 /tr "http://timestamp.acs.microsoft.com" /td SHA256 `
    /dlib $DlibPath /dmdf $metadataPath $msixPath
if ($LASTEXITCODE -ne 0) { throw "Azure Trusted Signing failed." }

$signature = Get-AuthenticodeSignature $msixPath
if ($signature.Status -ne "Valid") { throw "Authenticode verification failed: $($signature.StatusMessage)" }
if ($signature.SignerCertificate.Subject -ne $manifestPublisher) {
    throw "Signer '$($signature.SignerCertificate.Subject)' does not match manifest publisher '$manifestPublisher'."
}
if (-not $signature.TimeStamperCertificate) { throw "The MSIX signature has no timestamp certificate." }

& $signTool verify /pa /v $msixPath
if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed." }

gh release upload $tag $msixPath --repo $Repository --clobber
if ($LASTEXITCODE -ne 0) { throw "Could not upload signed MSIX to release $tag." }

Write-Host "Published verified signed MSIX: $msixPath" -ForegroundColor Green
Write-Host "Signer: $($signature.SignerCertificate.Subject)"
Write-Host "Timestamp: $($signature.TimeStamperCertificate.NotBefore)"