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
        global_admin_count = 3
        accounts = @("breakglass-admin", "cloud-admin-1", "cloud-admin-2")
      }
      message = "Global administrator count is within the expected range."
      score_contribution = 0
    }
  )
  metrics = [ordered]@{
    summary = "Global administrator local PowerShell collector executed"
    global_admin_count = 3
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
