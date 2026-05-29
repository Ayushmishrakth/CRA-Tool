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
Assert-CraModule "PnP.PowerShell"

$collector = $CollectorJson | ConvertFrom-Json
if (-not $collector.admin_url) {
  throw "SharePoint admin_url is required in collector manifest for Connect-SPOService/PnP collection."
}

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "sharepoint"
$files = New-Object System.Collections.Generic.List[string]

Connect-CraGraph -TenantId $TenantId -Scopes @("Reports.Read.All","Sites.Read.All","Directory.Read.All") -Collector $collector | Out-Null
Connect-CraPnP -Url $collector.admin_url -Collector $collector

$sites = Get-PnPTenantSite -Detailed |
  Select-Object Url,Title,Owner,Template,SharingCapability,StorageUsageCurrent,LastContentModifiedDate,LockState,SensitivityLabel
$path = Join-Path $out "sharepoint_sites.csv"; Export-CraCsv $sites $path; $files.Add($path)

$external = $sites | Select-Object Url,Title,SharingCapability,Owner
$path = Join-Path $out "external_sharing.csv"; Export-CraCsv $external $path; $files.Add($path)

$inactiveThreshold = (Get-Date).AddDays(-90)
$inactive = $sites | Where-Object { $_.LastContentModifiedDate -and $_.LastContentModifiedDate -lt $inactiveThreshold } |
  Select-Object Url,Title,Owner,LastContentModifiedDate,StorageUsageCurrent
$path = Join-Path $out "inactive_sites.csv"; Export-CraCsv $inactive $path; $files.Add($path)

$sharingLinks = foreach ($site in $sites) {
  [pscustomobject]@{
    Url = $site.Url
    Title = $site.Title
    SharingCapability = $site.SharingCapability
    EvidenceSource = "Get-PnPTenantSite"
  }
}
$path = Join-Path $out "sharing_links.csv"; Export-CraCsv $sharingLinks $path; $files.Add($path)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
