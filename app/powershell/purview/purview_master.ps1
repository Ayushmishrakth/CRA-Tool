param(
  [Parameter(Mandatory=$true)][string]$TenantId,
  [Parameter(Mandatory=$true)][string]$CollectorName,
  [Parameter(Mandatory=$true)][string]$ParameterKey,
  [Parameter(Mandatory=$true)][string]$ParameterJson,
  [Parameter(Mandatory=$true)][string]$CollectorJson,
  [Parameter(Mandatory=$true)][string]$AssessmentId,
  [Parameter(Mandatory=$true)][string]$OutputRoot
)

. (Join-Path $PSScriptRoot "../common/cra_common.ps1")
Assert-CraModule "ExchangeOnlineManagement"

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "purview"
$files = New-Object System.Collections.Generic.List[string]

Connect-IPPSSession -ErrorAction Stop | Out-Null

$dlp = Get-DlpCompliancePolicy | Select-Object Name,Mode,Enabled,Workload,ExchangeLocation,SharePointLocation,OneDriveLocation,TeamsLocation
$path = Join-Path $out "dlp_policies.csv"; Export-CraCsv $dlp $path; $files.Add($path)

$retention = Get-RetentionCompliancePolicy | Select-Object Name,Enabled,Mode,ExchangeLocation,SharePointLocation,OneDriveLocation,TeamsLocation
$path = Join-Path $out "retention_policies.csv"; Export-CraCsv $retention $path; $files.Add($path)

$audit = Get-AdminAuditLogConfig | Select-Object UnifiedAuditLogIngestionEnabled,AdminAuditLogEnabled,TestCmdletLoggingEnabled
$path = Join-Path $out "audit_logging.csv"; Export-CraCsv $audit $path; $files.Add($path)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
