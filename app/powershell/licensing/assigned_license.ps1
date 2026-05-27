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
      status = "pass"
      severity = "critical"
      value = [ordered]@{
        eligible_users = 112
        licensed_users = 108
        coverage_percent = 96.4
      }
      message = "Prerequisite license assignment coverage is above target."
      score_contribution = 0
    }
  )
  metrics = [ordered]@{
    summary = "License inventory local PowerShell collector executed"
    coverage_percent = 96.4
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
