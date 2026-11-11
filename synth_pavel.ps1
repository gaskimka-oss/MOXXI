param (
    [string]$Text,
    [string]$OutFile
)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType = WindowsRuntime] | Out-Null
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Id -like "*Pavel*" } | Select-Object -First 1
if (-not $voice) {
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -like "ru*" } | Select-Object -First 1
}
$synth.Voice = $voice
$op = $synth.SynthesizeTextToStreamAsync($Text)
$task = [System.WindowsRuntimeSystemExtensions]::AsTask($op)
$stream = $task.GetAwaiter().GetResult()

$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
$bytes = [byte[]]::new($stream.Size)
$loadTask = [System.WindowsRuntimeSystemExtensions]::AsTask($reader.LoadAsync($stream.Size))
$loadTask.GetAwaiter().GetResult() | Out-Null
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes($OutFile, $bytes)
Write-Host "Synthesized successfully to $OutFile ($($bytes.Length) bytes)"
