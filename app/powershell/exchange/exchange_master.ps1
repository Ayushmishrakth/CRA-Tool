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

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "exchange"
$files = New-Object System.Collections.Generic.List[string]

Connect-ExchangeOnline -ShowBanner:$false -ErrorAction Stop

$mailboxes = Get-EXOMailbox -ResultSize Unlimited -Properties AuditEnabled,ForwardingSmtpAddress,DeliverToMailboxAndForward,RecipientTypeDetails |
  Select-Object ExternalDirectoryObjectId,DisplayName,UserPrincipalName,RecipientTypeDetails,AuditEnabled
$path = Join-Path $out "mailbox_audit.csv"; Export-CraCsv $mailboxes $path; $files.Add($path)

$rules = Get-TransportRule | Select-Object Name,State,Mode,Priority,Comments
$path = Join-Path $out "transport_rules.csv"; Export-CraCsv $rules $path; $files.Add($path)

$forwarding = Get-EXOMailbox -ResultSize Unlimited -Properties ForwardingSmtpAddress,DeliverToMailboxAndForward |
  Where-Object { $_.ForwardingSmtpAddress -or $_.DeliverToMailboxAndForward } |
  Select-Object DisplayName,UserPrincipalName,ForwardingSmtpAddress,DeliverToMailboxAndForward
$path = Join-Path $out "mail_forwarding.csv"; Export-CraCsv $forwarding $path; $files.Add($path)

$safeLinks = Get-SafeLinksPolicy | Select-Object Name,IsEnabled,EnableSafeLinksForEmail,EnableSafeLinksForTeams
$path = Join-Path $out "safe_links.csv"; Export-CraCsv $safeLinks $path; $files.Add($path)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
