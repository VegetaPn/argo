# 使用真实 Chrome 浏览器避免 Twitter 检测

## 问题

Twitter 能检测到 Playwright/自动化浏览器，显示"此浏览器或应用可能不安全"错误。

## 解决方案

使用真实的 Chrome 浏览器 + CDP (Chrome DevTools Protocol) 连接，这样 Twitter 看到的是正常的 Chrome 浏览器。

## 设置步骤

### 1. 启动带调试端口的 Chrome

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.argo/chrome-profile" \
  https://twitter.com/login

# Linux
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.argo/chrome-profile" \
  https://twitter.com/login

# Windows (PowerShell)
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:USERPROFILE\.argo\chrome-profile" `
  https://twitter.com/login
```

**重要说明**：
- `--remote-debugging-port=9222`: 开启调试端口，让 agent-browser 可以连接
- `--user-data-dir`: 使用独立的配置文件目录，保存登录状态
- Chrome 窗口会保持打开，**不要关闭它**

### 2. 在 Chrome 中手动登录 Twitter

在打开的 Chrome 窗口中：
1. 正常登录 Twitter（输入用户名、密码、二步验证等）
2. 确认登录成功，能看到首页
3. **保持 Chrome 窗口打开**

### 3. 测试 agent-browser 连接

在另一个终端窗口中：

```bash
# 测试连接
agent-browser --cdp 9222 get url

# 应该输出：https://twitter.com/home 或类似的 Twitter URL
```

如果成功，说明连接正常！

### 4. 测试发布评论

```bash
# 使用 --cdp 模式测试
agent-browser --cdp 9222 open https://twitter.com/elonmusk/status/1234567890
agent-browser --cdp 9222 snapshot -i
```

## 修改代码使用 CDP 模式

修改 `argo/growth/cli/main.py`，让 BrowserClient 使用 CDP：

```python
self.browser = BrowserClient(
    delay=self.settings['rate_limit']['delay_seconds'],
    session_name="",
    headed=debug,
    use_cdp=True,  # 使用 CDP 模式
    cdp_port=9222  # CDP 端口
)
```

然后修改 `argo/growth/core/browser_client.py` 的 `_run_command` 方法：

```python
def _run_command(self, args: list[str], skip_rate_limit: bool = False) -> str:
    if not skip_rate_limit:
        self._rate_limit()

    command = ["agent-browser"]

    # 如果使用 CDP 模式，添加 --cdp 参数
    if hasattr(self, 'use_cdp') and self.use_cdp:
        command.extend(["--cdp", str(self.cdp_port)])
    # ... 其他逻辑
```

## 使用流程

### 每次使用前

1. **启动 Chrome**（如果还没启动）：
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir="$HOME/.argo/chrome-profile" \
     https://twitter.com/home
   ```

2. **确认登录状态**：
   - 如果已登录，直接进行下一步
   - 如果未登录，在 Chrome 中手动登录

3. **运行程序**：
   ```bash
   python main.py review
   # 或
   python main.py publish
   ```

4. **使用完毕后**：
   - 可以关闭 Chrome（登录状态会保存在 user-data-dir 中）
   - 下次启动 Chrome 时会自动恢复登录状态

## 优势

✅ **不会被检测** - Twitter 看到的是真实的 Chrome 浏览器
✅ **保持登录** - 使用 user-data-dir 保存配置和登录状态
✅ **手动控制** - Chrome 窗口可见，可以随时手动干预
✅ **调试方便** - 可以在 Chrome 中看到实际操作

## 自动化脚本

创建一个启动脚本 `start_chrome.sh`：

```bash
#!/bin/bash

# macOS
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="$HOME/.argo/chrome-profile"
CDP_PORT=9222

# 检查 Chrome 是否已经在运行
if lsof -Pi :$CDP_PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Chrome is already running on port $CDP_PORT"
else
    echo "🚀 Starting Chrome with CDP on port $CDP_PORT..."
    "$CHROME_PATH" \
      --remote-debugging-port=$CDP_PORT \
      --user-data-dir="$USER_DATA_DIR" \
      https://twitter.com/home &

    sleep 3
    echo "✅ Chrome started!"
fi

# 测试连接
echo "🔍 Testing connection..."
agent-browser --cdp $CDP_PORT get url
```

使用：
```bash
chmod +x start_chrome.sh
./start_chrome.sh
```

## 故障排查

### Q: 端口 9222 已被占用

```bash
# 查找占用的进程
lsof -i :9222

# 关闭占用的进程
kill <PID>
```

### Q: agent-browser 无法连接

```bash
# 检查 Chrome 是否在 9222 端口监听
lsof -i :9222

# 如果没有，重新启动 Chrome
```

### Q: Twitter 还是显示"浏览器不安全"

这不应该发生，因为我们使用的是真实的 Chrome。如果还是出现：
1. 确认使用的是 `--cdp 9222` 参数
2. 确认 Chrome 是正常启动的（不是 headless 模式）
3. 检查 Chrome 版本是否是最新的

### Q: 想关闭 Chrome 但保持登录

直接关闭 Chrome 即可，登录状态会保存在 `~/.argo/chrome-profile` 中。下次启动 Chrome 时会自动恢复。

## 完整工作流

```bash
# 1. 启动 Chrome（一次性设置）
./start_chrome.sh

# 2. 如果是首次使用，在 Chrome 中手动登录 Twitter

# 3. 正常使用
python main.py scan
python main.py review
python main.py publish

# 4. 关闭 Chrome（可选）
# 直接关闭窗口即可，登录状态会保存
```

就是这样！🚀
