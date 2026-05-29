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
Assert-CraModule "Microsoft.Graph"
$collector = $CollectorJson | ConvertFrom-Json

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "onedrive"
$files = New-Object System.Collections.Generic.List[string]

Connect-CraGraph -TenantId $TenantId -Scopes @("Reports.Read.All","Files.Read.All","Sites.Read.All") -Collector $collector | Out-Null

$period = "D180"
$usagePath = Join-Path $out "onedrive_usage.csv"
Get-MgReportOneDriveUsageAccountDetail -Period $period -OutFile $usagePath -ErrorAction Stop
if (-not (Test-Path $usagePath)) { throw "OneDrive usage CSV was not generated." }
$files.Add($usagePath)

$activityPath = Join-Path $out "onedrive_activity.csv"
Get-MgReportOneDriveActivityUserDetail -Period $period -OutFile $activityPath -ErrorAction Stop
if (-not (Test-Path $activityPath)) { throw "OneDrive activity CSV was not generated." }
$files.Add($activityPath)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
