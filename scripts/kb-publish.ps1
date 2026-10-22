# 把本机知识库发布到 NAS 的网页版（带登录：http://192.168.15.100:8899/）
# 用法: powershell -ExecutionPolicy Bypass -File kb-publish.ps1
$ErrorActionPreference = "Stop"
$kb    = "E:\deepseek\knowledge-base"
$tools = "E:\deepseek\kb-tools"
$key   = "$env:USERPROFILE\.ssh\id_ed25519"
$host_ = "root@192.168.15.100"
$dst   = "/vol1/1000/kb-web/"

# 1. 重建浏览页（使用 viewer-template.html）
& "D:\Python312\python.exe" "$tools\kb-build.py"

# 2. 同步到 NAS（网页、索引、条目和图片）
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=accept-new -q "$kb\index.html" "$kb\INDEX.md" "${host_}:$dst"
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=accept-new -q -r "$kb\douyin" "$kb\wechat" "$kb\notes" "$kb\_assets" "${host_}:$dst"

# 3. 确保登录服务在跑（服务脚本同步过去，不在就拉起来）
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=accept-new -q "$tools\kb-server.py" "${host_}:/vol1/1000/kb-server/kb-server.py"
$script = @'
cd /vol1/1000/kb-server
if ! pgrep -f "kb-server.py" >/dev/null; then
  setsid nohup python3 kb-server.py --root /vol1/1000/kb-web --port 8899 --users /vol1/1000/kb-server/kb-users.json > server.log 2>&1 < /dev/null &
  sleep 2
fi
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8899/index.html)
echo "服务状态: 未登录访问返回 $code（302=跳登录页，正常）"
'@
$b = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
ssh -i $key -o BatchMode=yes $host_ "echo $b | base64 -d | bash"
Write-Host "已发布: http://192.168.15.100:8899/（需登录）" -ForegroundColor Green
