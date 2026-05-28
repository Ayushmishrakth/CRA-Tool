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
Assert-CraModule "MicrosoftTeams"
Assert-CraModule "Microsoft.Graph"

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "teams"
$files = New-Object System.Collections.Generic.List[string]

Connect-MicrosoftTeams -TenantId $TenantId -ErrorAction Stop | Out-Null
Connect-MgGraph -TenantId $TenantId -Scopes @("Reports.Read.All","Group.Read.All","Team.ReadBasic.All") -NoWelcome -ErrorAction Stop | Out-Null

$teams = Get-Team | Select-Object GroupId,DisplayName,Visibility,Archived,MailNickName,Description
$path = Join-Path $out "teams_inventory.csv"; Export-CraCsv $teams $path; $files.Add($path)

$externalUsers = foreach ($team in $teams) {
  Get-TeamUser -GroupId $team.GroupId | Where-Object { $_.User -match "#EXT#|\.onmicrosoft\.com" } |
    Select-Object @{Name="GroupId";Expression={$team.GroupId}}, @{Name="Team";Expression={$team.DisplayName}}, User, Role
}
$path = Join-Path $out "teams_external_users.csv"; Export-CraCsv $externalUsers $path; $files.Add($path)

$meetingPolicies = Get-CsTeamsMeetingPolicy |
  Select-Object Identity,AllowCloudRecording,AllowTranscription,AllowAnonymousUsersToJoinMeeting,AutoAdmittedUsers,MeetingChatEnabledType,NewMeetingRecordingExpirationDays
$path = Join-Path $out "meeting_policies.csv"; Export-CraCsv $meetingPolicies $path; $files.Add($path)

$inactiveTeams = $teams | Where-Object { $_.Archived -eq $true } |
  Select-Object GroupId,DisplayName,Archived,Visibility
$path = Join-Path $out "inactive_teams.csv"; Export-CraCsv $inactiveTeams $path; $files.Add($path)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
