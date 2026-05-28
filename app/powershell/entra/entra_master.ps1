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
Assert-CraModule "Microsoft.Graph.Beta"

$out = Initialize-CraArtifactDirectory -OutputRoot $OutputRoot -AssessmentId $AssessmentId -Domain "entra"
$scopes = @(
  "Directory.Read.All",
  "Policy.Read.All",
  "Application.Read.All",
  "RoleManagement.Read.Directory",
  "AuditLog.Read.All",
  "UserAuthenticationMethod.Read.All"
)
Connect-MgGraph -TenantId $TenantId -Scopes $scopes -NoWelcome -ErrorAction Stop | Out-Null

$files = New-Object System.Collections.Generic.List[string]

$roles = Get-MgDirectoryRole -All
$globalAdmin = $roles | Where-Object DisplayName -eq "Global Administrator" | Select-Object -First 1
if ($globalAdmin) {
  $globalAdmins = Get-MgDirectoryRoleMember -DirectoryRoleId $globalAdmin.Id -All |
    Select-Object Id, AdditionalProperties
} else {
  $globalAdmins = @()
}
$path = Join-Path $out "global_admins.csv"; Export-CraCsv $globalAdmins $path; $files.Add($path)

$guests = Get-MgUser -All -Filter "userType eq 'Guest'" -Property "id,displayName,userPrincipalName,mail,accountEnabled,createdDateTime,signInActivity,userType" |
  Select-Object Id,DisplayName,UserPrincipalName,Mail,AccountEnabled,CreatedDateTime,UserType
$path = Join-Path $out "guest_users.csv"; Export-CraCsv $guests $path; $files.Add($path)

$users = Get-MgUser -All -Property "id,displayName,userPrincipalName,accountEnabled,createdDateTime,signInActivity,assignedLicenses"
$inactive = $users | Select-Object Id,DisplayName,UserPrincipalName,AccountEnabled,CreatedDateTime
$path = Join-Path $out "inactive_users.csv"; Export-CraCsv $inactive $path; $files.Add($path)

$mfa = Get-MgReportAuthenticationMethodUserRegistrationDetail -All |
  Select-Object Id,UserPrincipalName,UserDisplayName,IsMfaRegistered,IsMfaCapable,IsPasswordlessCapable,MethodsRegistered
$path = Join-Path $out "mfa_status.csv"; Export-CraCsv $mfa $path; $files.Add($path)

$ca = Get-MgIdentityConditionalAccessPolicy -All |
  Select-Object Id,DisplayName,State,CreatedDateTime,ModifiedDateTime
$path = Join-Path $out "conditional_access.csv"; Export-CraCsv $ca $path; $files.Add($path)

$apps = Get-MgApplication -All |
  Select-Object Id,AppId,DisplayName,SignInAudience,CreatedDateTime
$path = Join-Path $out "applications.csv"; Export-CraCsv $apps $path; $files.Add($path)

$authPolicy = Get-MgPolicyAuthorizationPolicy | Select-Object Id,DisplayName,DefaultUserRolePermissions,AllowedToSignUpEmailBasedSubscriptions,AllowedToUseSspr
$path = Join-Path $out "security_defaults.csv"; Export-CraCsv $authPolicy $path; $files.Add($path)

Write-CraContract -CollectorName $CollectorName -TenantId $TenantId -ParameterKey $ParameterKey -GeneratedFiles $files.ToArray()
