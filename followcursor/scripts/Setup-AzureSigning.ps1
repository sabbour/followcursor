<#
.SYNOPSIS
    Provisions Azure Trusted Signing resources for local MSIX signing.

.DESCRIPTION
    This script is idempotent — safe to re-run if a step fails partway.

    Steps:
    1. Register the Microsoft.CodeSigning resource provider
    2. Create a resource group
    3. Create a Trusted Signing account
    4. Create a certificate profile (PublicTrust)
    5. Assign the signed-in Azure user the certificate profile signer role

.PARAMETER Location
    Azure region for the Trusted Signing account. Must be a region
    that supports Trusted Signing (e.g. eastus, westus, westeurope).

.PARAMETER ResourceGroupName
    Name of the resource group to create or use.

.PARAMETER AccountName
    Name of the Trusted Signing account.

.PARAMETER CertificateProfileName
    Name of the certificate profile.

.EXAMPLE
    .\Setup-AzureSigning.ps1
#>

#Requires -Version 7.0

param(
    [Parameter(Mandatory)]
    [string]$Location,

    [Parameter(Mandatory)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory)]
    [string]$AccountName,

    [Parameter(Mandatory)]
    [string]$CertificateProfileName
)

$ErrorActionPreference = "Stop"

# ── Helpers ─────────────────────────────────────────────────────
function Write-Step { param([string]$msg) Write-Host "`n> $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Skip { param([string]$msg) Write-Host "  SKIP: $msg (already exists)" -ForegroundColor Yellow }

# ── Prerequisites ───────────────────────────────────────────────
Write-Step "Checking prerequisites"
$sub = az account show --query "{id:id, tenantId:tenantId}" -o json | ConvertFrom-Json
if (-not $sub) { throw "Not logged in to Azure CLI. Run 'az login' first." }
$subscriptionId = $sub.id
Write-OK "Subscription: $subscriptionId"
Write-OK "Tenant: $($sub.tenantId)"

# ── 1. Register resource provider ──────────────────────────────
Write-Step "Registering Microsoft.CodeSigning resource provider"
$providerState = az provider show --namespace Microsoft.CodeSigning --query "registrationState" -o tsv 2>$null
if ($providerState -eq "Registered") {
    Write-Skip "Microsoft.CodeSigning already registered"
} else {
    az provider register --namespace Microsoft.CodeSigning --wait
    Write-OK "Registered Microsoft.CodeSigning"
}

# ── 2. Create resource group ───────────────────────────────────
Write-Step "Creating resource group: $ResourceGroupName"
$rgExists = az group exists --name $ResourceGroupName -o tsv
if ($rgExists -eq "true") {
    Write-Skip "Resource group $ResourceGroupName"
} else {
    az group create --name $ResourceGroupName --location $Location -o none
    Write-OK "Created $ResourceGroupName in $Location"
}

# ── 3. Create Trusted Signing account ──────────────────────────
Write-Step "Creating Trusted Signing account: $AccountName"
$acctExists = $null
try {
    $acctExists = az resource show --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts" `
        --name $AccountName --query "id" -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) { $acctExists = $null }
} catch { $acctExists = $null }
if ($acctExists) {
    Write-Skip "Trusted Signing account $AccountName"
} else {
    az resource create `
        --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts" `
        --name $AccountName `
        --location $Location `
        --properties '{"sku":{"name":"Basic"}}' `
        -o none
    Write-OK "Created Trusted Signing account $AccountName"
}

# Get the account endpoint
$acctEndpoint = $null
try {
    $acctEndpoint = az resource show --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts" `
        --name $AccountName --query "properties.accountUri" -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) { $acctEndpoint = $null }
} catch { $acctEndpoint = $null }
if (-not $acctEndpoint) {
    # Construct the endpoint from the location
    $acctEndpoint = "https://$Location.codesigning.azure.net"
}
Write-OK "Endpoint: $acctEndpoint"

# ── 4. Create certificate profile ──────────────────────────────
Write-Step "Creating certificate profile: $CertificateProfileName"
$profileExists = $null
try {
    $profileExists = az resource show --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts/certificateProfiles" `
        --name "$AccountName/$CertificateProfileName" --query "id" -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) { $profileExists = $null }
} catch { $profileExists = $null }
if ($profileExists) {
    $profileType = az resource show --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts/certificateProfiles" `
        --name "$AccountName/$CertificateProfileName" `
        --query "properties.profileType" -o tsv
    if ($profileType -ne "PublicTrust") {
        throw "Certificate profile $CertificateProfileName uses $profileType. Public releases require a PublicTrust profile."
    }
    Write-Skip "PublicTrust certificate profile $CertificateProfileName"
} else {
    az resource create `
        --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts/certificateProfiles" `
        --name "$AccountName/$CertificateProfileName" `
        --properties (@{
            profileType = "PublicTrust"
            includeCity = $false
            includeState = $false
            includePostalCode = $false
            includeStreetAddress = $false
        } | ConvertTo-Json) `
        -o none
    Write-OK "Created certificate profile $CertificateProfileName"
}

# Get the publisher (subject name) from the certificate profile
$publisher = $null
try {
    $publisher = az resource show --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CodeSigning/codeSigningAccounts/certificateProfiles" `
        --name "$AccountName/$CertificateProfileName" `
        --query "properties.certificates[0].subjectName" -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) { $publisher = $null }
} catch { $publisher = $null }
if (-not $publisher) {
    throw "The PublicTrust certificate is not ready. Wait for the profile to become active, then run this script again."
}
Write-OK "Publisher: $publisher"

# ── 5. Assign Artifact Signing Certificate Profile Signer role ──
Write-Step "Assigning 'Artifact Signing Certificate Profile Signer' role"
$signingAccountId = az resource show --resource-group $ResourceGroupName `
    --resource-type "Microsoft.CodeSigning/codeSigningAccounts" `
    --name $AccountName --query "id" -o tsv
$signedInUserId = az ad signed-in-user show --query "id" -o tsv
if (-not $signedInUserId) { throw "Could not resolve the signed-in Azure user." }

$roleAssigned = $null
try {
    $roleAssigned = az role assignment list --assignee $signedInUserId --scope $signingAccountId `
        --role "Artifact Signing Certificate Profile Signer" --query "[0].id" -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) { $roleAssigned = $null }
} catch { $roleAssigned = $null }
if ($roleAssigned) {
    Write-Skip "Role already assigned"
} else {
    az role assignment create `
        --assignee-object-id $signedInUserId `
        --assignee-principal-type User `
        --role "Artifact Signing Certificate Profile Signer" `
        --scope $signingAccountId `
        -o none
    Write-OK "Role assigned"
}

# ── Done ────────────────────────────────────────────────────────
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "  Azure Trusted Signing setup complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Subscription:       $subscriptionId"
Write-Host "  Resource Group:     $ResourceGroupName"
Write-Host "  Signing Account:    $AccountName"
Write-Host "  Certificate Profile:$CertificateProfileName"
Write-Host "  Endpoint:           $acctEndpoint"
Write-Host "  Publisher:          $publisher"
Write-Host ""
Write-Host "  Next: use Publish-SignedMsix.ps1 after the tag workflow succeeds." -ForegroundColor Yellow
