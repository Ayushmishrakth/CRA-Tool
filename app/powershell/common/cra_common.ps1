$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Initialize-CraArtifactDirectory {
  param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$AssessmentId,
    [Parameter(Mandatory=$true)][string]$Domain
  )
  $path = Join-Path $OutputRoot $AssessmentId
  $path = Join-Path $path $Domain
  New-Item -ItemType Directory -Path $path -Force | Out-Null
  return (Resolve-Path $path).Path
}

function Assert-CraModule {
  param([Parameter(Mandatory=$true)][string]$Name)
  if (-not (Get-Module -ListAvailable -Name $Name)) {
    throw "Required PowerShell module '$Name' is not installed. Run scripts/install_m365_modules.ps1."
  }
  Import-Module $Name -ErrorAction Stop
}

function Export-CraCsv {
  param(
    [Parameter(Mandatory=$true)]$InputObject,
    [Parameter(Mandatory=$true)][string]$Path
  )
  $InputObject | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
  if (-not (Test-Path $Path)) {
    throw "CSV evidence file was not created: $Path"
  }
}

function Write-CraContract {
  param(
    [Parameter(Mandatory=$true)][string]$CollectorName,
    [Parameter(Mandatory=$true)][string]$TenantId,
    [Parameter(Mandatory=$true)][string]$ParameterKey,
    [Parameter(Mandatory=$true)][string[]]$GeneratedFiles,
    [string[]]$Warnings = @()
  )
  $result = [ordered]@{
    status = "success"
    collector = $CollectorName
    tenant_id = $TenantId
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    findings = @(
      [ordered]@{
        parameter_key = $ParameterKey
        status = "not_collected"
        severity = "info"
        value = [ordered]@{
          generated_files = $GeneratedFiles
        }
        message = "Evidence CSV files were generated; finding evaluation must be performed by the CSV finding engine."
        score_contribution = 0
      }
    )
    metrics = [ordered]@{
      generated_files = $GeneratedFiles
      generated_file_count = $GeneratedFiles.Count
    }
    warnings = $Warnings
    errors = @()
  }
  $result | ConvertTo-Json -Depth 8 -Compress
}
