param(
  [Parameter(Mandatory=$true)][string]$TenantId,
  [Parameter(Mandatory=$true)][string]$CollectorName,
  [Parameter(Mandatory=$true)][string]$ParameterKey,
  [Parameter(Mandatory=$true)][string]$ParameterJson,
  [Parameter(Mandatory=$true)][string]$CollectorJson
)

$secureScore = 68
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
        secure_score_percent = $secureScore
        target_percent = 80
      }
      message = "Secure Score is below the readiness target."
      score_contribution = 2.25
    }
  )
  metrics = [ordered]@{
    summary = "Secure Score local PowerShell collector executed"
    secure_score_percent = $secureScore
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
