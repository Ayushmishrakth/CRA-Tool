param(
  [Parameter(Mandatory=$true)][string]$TenantId,
  [Parameter(Mandatory=$true)][string]$CollectorName,
  [Parameter(Mandatory=$true)][string]$ParameterKey,
  [Parameter(Mandatory=$true)][string]$ParameterJson,
  [Parameter(Mandatory=$true)][string]$CollectorJson
)

$result = [ordered]@{
  status = "success"
  collector = $CollectorName
  tenant_id = $TenantId
  timestamp = (Get-Date).ToUniversalTime().ToString("o")
  findings = @(
    [ordered]@{
      parameter_key = $ParameterKey
      status = "warning"
      severity = "critical"
      value = [ordered]@{
        total_capable_users = 128
        users_without_mfa = 7
        coverage_percent = 94.5
      }
      message = "MFA coverage is below the enterprise target for all capable users."
      score_contribution = 2.25
    }
  )
  metrics = [ordered]@{
    summary = "MFA coverage local PowerShell collector executed"
    coverage_percent = 94.5
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
