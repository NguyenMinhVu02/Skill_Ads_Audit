# Antigravity / Claude / Codex Skill Installer for infinity-ads-compliance-audit (Windows PowerShell)

$SkillName = "infinity-ads-compliance-audit"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗"
Write-Host "║   🚀 Skill Installer: $SkillName      ║"
Write-Host "╚══════════════════════════════════════════════════════════╝"
Write-Host ""

$Targets = @()

$GeminiPath = "$HOME\.gemini\antigravity\skills\$SkillName"
$ClaudePath = "$HOME\.claude\skills\$SkillName"
$AgentsPath = "$HOME\.agents\skills\$SkillName"
# Codex reads $CODEX_HOME/skills, which defaults to ~/.codex/skills
$CodexHome  = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$HOME\.codex" }
$CodexPath  = "$CodexHome\skills\$SkillName"

if (Test-Path "$HOME\.gemini") {
    $Targets += $GeminiPath
}
if (Test-Path "$HOME\.claude") {
    $Targets += $ClaudePath
}
if (Test-Path $CodexHome) {
    $Targets += $CodexPath
}
if (Test-Path "$HOME\.agents") {
    $Targets += $AgentsPath
}
if ($Targets.Count -eq 0) {
    $Targets += $GeminiPath
}

Write-Host "⏳ Installing skill files..."
foreach ($Target in $Targets) {
    if (!(Test-Path -Path $Target)) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
    }
    Get-ChildItem -Path $ScriptDir -Exclude ".git", "CLAUDE.md", "__pycache__", "ads-audit-output", "node_modules" | Copy-Item -Destination $Target -Recurse -Force
    Write-Host "   ✅ Installed to: $Target"
}

Write-Host ""
Write-Host "🎉 Skill '$SkillName' installed successfully!"
Write-Host ""
