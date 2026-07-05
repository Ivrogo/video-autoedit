# Genera test_clip.mp4: ~20s de narración TTS en español con pausas largas,
# para probar el pipeline (corte de silencios + transcripción + subtítulos).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\make_test_clip.ps1

$ErrorActionPreference = "Stop"
$work = Join-Path $env:TEMP "autoedit_testclip"
New-Item -ItemType Directory -Force $work | Out-Null

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

# Elegir una voz en español si existe
$esVoice = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -like "es-*" } |
    Select-Object -First 1
if ($esVoice) {
    $synth.SelectVoice($esVoice.VoiceInfo.Name)
    Write-Host "Voz: $($esVoice.VoiceInfo.Name)"
} else {
    Write-Warning "No hay voz en español instalada; se usará la voz por defecto."
}

$frases = @(
    "Hola, esto es una prueba del editor de video automático.",
    "Ahora viene una pausa larga que debería ser eliminada.",
    "Si puedes leer estos subtítulos, la transcripción ha funcionado correctamente.",
    "Fin de la prueba."
)

$parts = @()
for ($i = 0; $i -lt $frases.Count; $i++) {
    $wav = Join-Path $work "parte$i.wav"
    $synth.SetOutputToWaveFile($wav)
    $synth.Speak($frases[$i])
    $synth.SetOutputToNull()
    $parts += $wav
}
$synth.Dispose()

# Unir las frases con 3 segundos de silencio entre ellas
$silence = Join-Path $work "silencio.wav"
ffmpeg -hide_banner -y -f lavfi -i "anullsrc=r=22050:cl=mono" -t 3 -c:a pcm_s16le $silence

$listFile = Join-Path $work "lista.txt"
$lines = @()
for ($i = 0; $i -lt $parts.Count; $i++) {
    $lines += "file '" + ($parts[$i] -replace "\\", "/") + "'"
    if ($i -lt $parts.Count - 1) {
        $lines += "file '" + ($silence -replace "\\", "/") + "'"
    }
}
Set-Content -Path $listFile -Value $lines -Encoding ascii

$audio = Join-Path $work "narracion.wav"
ffmpeg -hide_banner -y -f concat -safe 0 -i $listFile -ar 22050 -ac 1 -c:a pcm_s16le $audio

# Video de fondo (testsrc2) con la narración encima
ffmpeg -hide_banner -y -f lavfi -i "testsrc2=size=1280x720:rate=30" -i $audio `
    -map 0:v -map 1:a -shortest `
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac -b:a 128k `
    test_clip.mp4

Remove-Item -Recurse -Force $work
Write-Host "Creado test_clip.mp4 en $(Get-Location)"
