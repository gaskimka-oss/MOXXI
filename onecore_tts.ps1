$src = @'
using System;
using System.IO;
using System.Threading.Tasks;
using Windows.Media.SpeechSynthesis;
using Windows.Storage.Streams;

public class OneCoreTTS {
    public static void Speak(string text, string outFile) {
        var synth = new SpeechSynthesizer();
        foreach (var v in SpeechSynthesizer.AllVoices) {
            if (v.Id.Contains("Pavel") || v.Language.StartsWith("ru")) {
                synth.Voice = v;
                break;
            }
        }
        var op = synth.SynthesizeTextToStreamAsync(text);
        var t = WindowsRuntimeSystemExtensions.AsTask(op);
        t.Wait();
        using (var stream = t.Result) {
            using (var reader = new DataReader(stream.GetInputStreamAt(0))) {
                var loadTask = WindowsRuntimeSystemExtensions.AsTask(reader.LoadAsync((uint)stream.Size));
                loadTask.Wait();
                byte[] bytes = new byte[stream.Size];
                reader.ReadBytes(bytes);
                File.WriteAllBytes(outFile, bytes);
            }
        }
    }
}
'@

Add-Type -TypeDefinition $src -ReferencedAssemblies 'System.Runtime.WindowsRuntime.dll', 'C:\Windows\System32\WinMetadata\Windows.Media.winmd', 'C:\Windows\System32\WinMetadata\Windows.Storage.winmd'
[OneCoreTTS]::Speak($args[0], $args[1])
Write-Host "Success! Generated file: $args[1]"
