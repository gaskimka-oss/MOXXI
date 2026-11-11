[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType = WindowsRuntime] | Out-Null
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voices = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
foreach ($v in $voices) {
    if ($v.Language -like "ru*") {
        Write-Host "$($v.DisplayName) | $($v.Id) | $($v.Gender)"
    }
}
