param(
  [Parameter(Mandatory=$true)][string]$TenantId,
  [Parameter(Mandatory=$true)][string]$CollectorName,
  [Parameter(Mandatory=$true)][string]$ParameterKey,
  [Parameter(Mandatory=$true)][string]$ParameterJson,
  [Parameter(Mandatory=$true)][string]$CollectorJson
)

$parameter = $ParameterJson | ConvertFrom-Json
$collector = $CollectorJson | ConvertFrom-Json
$statusOptions = @("pass", "warning", "fail")
$hash = [Math]::Abs($ParameterKey.GetHashCode())
$findingStatus = $statusOptions[$hash % $statusOptions.Count]
$severity = if ($parameter.severity) { $parameter.severity } else { "info" }
$score = if ($findingStatus -eq "pass") { 0 } elseif ($findingStatus -eq "warning") { 1 } else { 2 }

$result = [ordered]@{
  status = "success"
  collector = $CollectorName
  tenant_id = $TenantId
  timestamp = (Get-Date).ToUniversalTime().ToString("o")
  findings = @(
    [ordered]@{
      parameter_key = $ParameterKey
      status = $findingStatus
      severity = $severity
      value = [ordered]@{
        source = "local_mock"
        collector_type = $collector.collector_type
        observed_count = 10 + ($hash % 90)
      }
      message = "PowerShell local mock result for $($parameter.display_name)"
      score_contribution = $score
    }
  )
  metrics = [ordered]@{
    summary = "Executed generic PowerShell collector contract"
    collector_type = $collector.collector_type
  }
  warnings = @()
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
