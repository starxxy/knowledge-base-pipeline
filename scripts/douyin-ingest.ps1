# 抖音一键入库：分享链接 → 浏览器取流 → 下载/合并 → GPU 转写 → 条目草稿 + 索引
# 用法: powershell -ExecutionPolicy Bypass -File douyin-ingest.ps1 -Url "https://v.douyin.com/xxxx/" [-Title ""] [-Author ""] [-DryRun]
# 取流策略：先回 about:blank 清掉上一页网络噪音，再打开目标页；从网络日志拿候选直链，
#           逐个下载用 ffprobe 识别（合流/分轨），并用页面时长校验，避免拿到旧地址。
param(
  [Parameter(Mandatory = $true)][string]$Url,
  [string]$Title = "",
  [string]$Author = "",
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"

# ---------- 配置 ----------
$cfgPath = Join-Path (Split-Path $PSScriptRoot -Parent) "config.json"
$cfg = @{}
if (Test-Path $cfgPath) {
  (Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $cfg[$_.Name] = $_.Value }
}
function Conf($key, $default) {
  $envName = "KB_" + $key.ToUpper()
  if (Test-Path "env:$envName") { return (Get-Item "env:$envName").Value }
  if ($cfg.ContainsKey($key) -and $cfg[$key]) { return $cfg[$key] }
  return $default
}

$kb       = Conf "home" (Join-Path $env:USERPROFILE "knowledge-base")
$mediaDir = Conf "media_dir" (Join-Path $kb "_media_nas")
$python   = Conf "python" "python"
$agentSession = Conf "agent_browser_session" "kb-douyin"
$audioDir = Join-Path $kb "_media"
$draftDir = Join-Path $kb "douyin"
$tools    = $PSScriptRoot

$env:PATH = (Join-Path $env:APPDATA "npm") + ";" + $env:PATH
$env:AGENT_BROWSER_SESSION = $agentSession
$ua  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
$ref = "https://www.douyin.com/"

foreach ($d in @($audioDir, $draftDir, $mediaDir)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

# ---------- 1. 浏览器取流 ----------
$t0 = Get-Date
& agent-browser open 2>&1 | Out-Null
& agent-browser network requests --clear 2>&1 | Out-Null
& agent-browser open $Url 2>&1 | Out-Null

$playJs = @'
(async()=>{const v=document.querySelector('video'); if(v){v.muted=true; try{await v.play()}catch(e){}} return 'ok';})()
'@
$playB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($playJs))

$candidates = @()
$meta = $null
for ($i = 0; $i -lt 25; $i++) {
  & agent-browser eval "eval(atob('$playB64'))" 2>$null | Out-Null
  Start-Sleep -Milliseconds 700
  $log = (& agent-browser network requests --filter douyinvod 2>$null | Out-String)
  $candidates = @([regex]::Matches($log, 'GET (https://[^\s]+)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
  if ($candidates.Count -gt 0) {
    $metaJs = @'
(()=>{const m=location.href.match(/\/video\/(\d+)/);const v=document.querySelector('video');return JSON.stringify({href:location.href,title:document.title.replace(/\s*-\s*抖音\s*$/,''),id:m?m[1]:null,dur:v?v.duration:null});})()
'@
    $metaB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($metaJs))
    $raw = (& agent-browser eval "eval(atob('$metaB64'))" 2>$null | Out-String).Trim()
    try {
      $obj = $raw | ConvertFrom-Json
      if ($obj -is [string]) { $obj = $obj | ConvertFrom-Json }
      $meta = $obj
    } catch { }
    if ($meta -and $meta.dur) { break }
  }
}
if ($candidates.Count -eq 0) { Write-Error "未取到视频直链（页面可能需登录/验证）"; exit 1 }
if (-not $meta) { $meta = [pscustomobject]@{ id = $null; title = ""; href = $Url; dur = $null } }

# ---------- 2. 标题 / ID / 文件名 ----------
$id = $meta.id
if (-not $id) { $id = [DateTimeOffset]::Now.ToUnixTimeSeconds() }
if (-not $Title) { $Title = $meta.title }
if (-not $Title) { $Title = "抖音视频 $id" }
$hashTags = @([regex]::Matches($Title, '#([^\s#]+)') | ForEach-Object { $_.Groups[1].Value })
$Title = (($Title -replace '#[^\s#]+', '') -replace '\s*-\s*抖音\s*$', '').Trim()
$Title = ($Title -replace '\s{2,}', ' ').Trim()
if (-not $Title) { $Title = "抖音视频 $id" }
$tagLine = if ($hashTags.Count -gt 0) { ($hashTags -join ', ') } else { '' }

$safeTitle = ($Title -replace '[\\/:*?"<>|\r\n\t]', '_').Trim().TrimEnd('.')
if ($safeTitle.Length -gt 80) { $safeTitle = $safeTitle.Substring(0, 80).TrimEnd() }
if (-not $safeTitle) { $safeTitle = "抖音视频 $id" }

$video = Join-Path $mediaDir "$safeTitle.mp4"
if ((Test-Path $video) -and -not (Test-Path (Join-Path $draftDir "$id.md"))) { $video = Join-Path $mediaDir "$safeTitle`_$id.mp4" }
Write-Host "取流完成: $id / $Title（页面 $($meta.dur)s，$([math]::Round(((Get-Date)-$t0).TotalSeconds,1))s）" -ForegroundColor Green

# ---------- 3. 候选直链逐个下载并识别 ----------
$candVideo = $null; $candAudio = $null; $combined = $null; $n = 0
foreach ($u in ($candidates | Select-Object -First 8)) {
  $n++
  $tmp = Join-Path $env:TEMP "dy_cand_${id}_$n.mp4"
  curl.exe -L -s -o $tmp -e $ref -A $ua "$u"
  if (-not (Test-Path $tmp) -or (Get-Item $tmp).Length -lt 10000) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue; continue }
  $streams = (& ffprobe -v error -show_entries stream=codec_type -of csv=p=0 $tmp 2>$null) -join ','
  $hasV = $streams -match 'video'; $hasA = $streams -match 'audio'
  if ($hasV -and $hasA) { $combined = $tmp; break }
  if ($hasV -and -not $candVideo) { $candVideo = $tmp; continue }
  if ($hasA -and -not $candAudio) { $candAudio = $tmp; continue }
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

# ---------- 4. 落盘 ----------
if ($combined) {
  Copy-Item -Force $combined "$video.tmp"
} elseif ($candVideo) {
  if ($candAudio) {
    $muxed = Join-Path $env:TEMP "dy_mux_$id.mp4"
    ffmpeg -y -v error -i $candVideo -i $candAudio -c copy -shortest $muxed
    Copy-Item -Force $muxed "$video.tmp"
  } else {
    Copy-Item -Force $candVideo "$video.tmp"
  }
} else { Write-Error "所有候选直链都下载失败"; exit 1 }
Move-Item -Force "$video.tmp" $video
Get-ChildItem $env:TEMP -Filter "dy_cand_${id}_*.mp4" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

$duration = [math]::Round([double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $video 2>$null), 1)
if ($meta.dur -and [math]::Abs($duration - [double]$meta.dur) -gt 2) {
  Remove-Item -Force $video -ErrorAction SilentlyContinue
  Write-Error "下载内容与页面不符（页面 $([math]::Round([double]$meta.dur,1))s / 文件 ${duration}s），已清理"
  exit 1
}

# ---------- 5. 音频 + 转写 ----------
$audio = Join-Path $audioDir "$id.mp3"
ffmpeg -y -v error -i $video -vn -acodec libmp3lame -q:a 4 $audio 2>&1 | Out-Null
$transcriptFile = Join-Path $env:TEMP "transcript_$id.txt"
Remove-Item $transcriptFile -Force -ErrorAction SilentlyContinue
$tr = Start-Process -FilePath $python -ArgumentList @((Join-Path $tools "transcribe.py"), $audio, $transcriptFile) -PassThru -WindowStyle Hidden
$tr.WaitForExit()
if (-not (Test-Path $transcriptFile)) { Write-Error "转写未产出"; exit 1 }
$transcript = (Get-Content $transcriptFile -Raw -Encoding UTF8).TrimEnd()

if ($DryRun) { Write-Host "DRYRUN OK id=$id duration=$duration chars=$($transcript.Length) video=$video" -ForegroundColor Cyan; exit 0 }

# ---------- 6. 条目草稿 + 索引 ----------
$now = Get-Date -Format "yyyy-MM-dd HH:mm"
$draft = Join-Path $draftDir "$id.md"
@"
---
类型: 抖音视频
原链接: $Url
视频ID: $id
视频标题: $Title
作者: $Author
发布时间:
视频时长: ${duration}s
解析时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
入库时间: $now
NAS归档路径: $video
标签: [$tagLine]
---

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 金句 / 可复用片段
（待提炼）

## 逐字稿（全文）
``````
$transcript
``````

## 元信息
- 视频原件: $video（$((Get-Item $video).Length) bytes，${duration}s）
- 音轨: _media\$id.mp3（转写用临时音频，可清理）
"@ | Set-Content -Encoding UTF8 $draft

$index = Join-Path $kb "INDEX.md"
if (-not (Test-Path $index)) { "# 知识库总索引`n`n| 入库时间 | 类型 | 标题 | 标签 | 原链接 | 条目 |`n|---|---|---|---|---|---|`n" | Set-Content -Encoding UTF8 $index }
$indexTags = if ($tagLine) { $tagLine -replace ',\s*', '/' } else { '待补' }
$row = "| $now | 抖音视频 | $Title | $indexTags | $Url | [条目](douyin/$id.md) |"
$lines = Get-Content $index -Encoding UTF8
$out = New-Object System.Collections.Generic.List[string]; $inserted = $false
foreach ($l in $lines) {
  if ($l -match [regex]::Escape("(douyin/$id.md)")) { continue }
  $out.Add($l)
  if (-not $inserted -and $l -match '^\|[-|]+\|$') { $out.Add($row); $inserted = $true }
}
if (-not $inserted) { $out.Add($row) }
Set-Content -Path $index -Value $out -Encoding UTF8

Write-Host "`n=== 完成 ===" -ForegroundColor Cyan
Write-Host "条目: $draft"
Write-Host "转写: $($transcript.Length) 字"
Write-Host "下一步：读逐字稿回填「一句话总结 / 核心内容 / 金句」，然后跑 kb-build.py"
