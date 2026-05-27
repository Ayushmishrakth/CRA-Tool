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
      severity = "medium"
      value = [ordered]@{
        teams_with_external_users = 4
        reviewed_teams = 42
      }
      message = "Some Teams include external users and require owner review."
      score_contribution = 1.35
    }
  )
  metrics = [ordered]@{
    summary = "Teams external users local PowerShell collector executed"
    teams_with_external_users = 4
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
