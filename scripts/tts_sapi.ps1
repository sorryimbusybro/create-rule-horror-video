param(
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [int]$Rate = -1,
    [string]$Voice = "",
    [switch]$Force
)

# Offline Windows fallback voice. Optional: only use when the user has no voiceover
# and no ElevenLabs export. Requires Windows PowerShell with System.Speech.
# Run manually if your agent policy blocks speech synthesis:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tts_sapi.ps1 -ProjectRoot "C:\path\to\project"

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$projectPath = Join-Path $ProjectRoot "project.json"
if (-not (Test-Path $projectPath)) { throw "Missing project.json in $ProjectRoot" }

$project = Get-Content -Raw -Encoding UTF8 $projectPath | ConvertFrom-Json
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer

if ($Voice -ne "") {
    $synthesizer.SelectVoice($Voice)
} else {
    $installed = $synthesizer.GetInstalledVoices() | Where-Object { $_.Enabled }
    $male = $installed | Where-Object { $_.VoiceInfo.Gender -eq "Male" } | Select-Object -First 1
    if ($male) { $synthesizer.SelectVoice($male.VoiceInfo.Name) }
}

$synthesizer.Rate = $Rate
$synthesizer.Volume = 100
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    48000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono
)

$total = $project.beats.Count
$index = 0

try {
    foreach ($beat in $project.beats) {
        $index++
        $id = [string]$beat.id
        if ($id -eq "") { throw "Beat at position $index has no id" }
        $relative = "assets/audio/$id.wav"
        $output = Join-Path $ProjectRoot ($relative -replace '/', '\')
        $folder = Split-Path -Parent $output
        if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
        if ((Test-Path $output) -and -not $Force) { continue }

        $text = [string]$beat.narration
        if ($text.Trim() -eq "") { throw "Beat $id has no narration" }

        $synthesizer.SetOutputToWaveFile($output, $format)
        $synthesizer.Speak($text)
        $synthesizer.SetOutputToNull()

        if (($index % 10) -eq 0 -or $index -eq $total) {
            Write-Output "Narration progress: $index/$total beats"
        }
    }
}
finally {
    $synthesizer.Dispose()
}

Write-Output "SAPI narration complete at rate $Rate"
Write-Output "Next: python video_pipeline.py audio `"$ProjectRoot`" --source `"$ProjectRoot\assets\audio`""
