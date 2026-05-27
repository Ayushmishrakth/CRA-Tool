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
        sharepoint_external_sharing = "ExistingExternalUserSharingOnly"
        onedrive_external_sharing = "ExistingExternalUserSharingOnly"
      }
      message = "External sharing is enabled and should be reviewed for Copilot readiness."
      score_contribution = 2.25
    }
  )
  metrics = [ordered]@{
    summary = "SharePoint external sharing local PowerShell collector executed"
  }
  warnings = @("Uses local mocked data until Microsoft Graph collectors are enabled.")
  errors = @()
}

$result | ConvertTo-Json -Depth 8 -Compress
