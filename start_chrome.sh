#!/bin/bash

# Chrome 路径（macOS）
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR="$HOME/.argo/chrome-profile"
CDP_PORT=9222

# 检查 Chrome 是否已经在运行
if lsof -Pi :$CDP_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "✅ Chrome is already running on port $CDP_PORT"

    # 测试连接
    echo "🔍 Testing connection..."
    if agent-browser --cdp $CDP_PORT get url >/dev/null 2>&1 ; then
        CURRENT_URL=$(agent-browser --cdp $CDP_PORT get url 2>/dev/null | head -1)
        echo "✅ Connected! Current URL: $CURRENT_URL"
    else
        echo "⚠️  Chrome is running but agent-browser cannot connect"
        echo "   Try restarting Chrome"
    fi
else
    echo "🚀 Starting Chrome with CDP on port $CDP_PORT..."

    # 检查 Chrome 是否存在
    if [ ! -f "$CHROME_PATH" ]; then
        echo "❌ Chrome not found at: $CHROME_PATH"
        echo "Please update CHROME_PATH in this script"
        exit 1
    fi

    # 创建用户数据目录
    mkdir -p "$USER_DATA_DIR"

    # 启动 Chrome
    "$CHROME_PATH" \
      --remote-debugging-port=$CDP_PORT \
      --user-data-dir="$USER_DATA_DIR" \
      https://twitter.com/home &

    sleep 3

    # 测试连接
    echo "🔍 Testing connection..."
    if agent-browser --cdp $CDP_PORT get url >/dev/null 2>&1 ; then
        echo "✅ Chrome started and connected!"
        CURRENT_URL=$(agent-browser --cdp $CDP_PORT get url 2>/dev/null | head -1)
        echo "   Current URL: $CURRENT_URL"
        echo ""
        echo "📝 Next steps:"
        echo "   1. Login to Twitter in the Chrome window (if not already logged in)"
        echo "   2. Run: python main.py review"
    else
        echo "⚠️  Chrome started but connection failed"
        echo "   Please wait a moment and try again"
    fi
fi

echo ""
echo "ℹ️  To stop Chrome: killall 'Google Chrome'"
echo "ℹ️  Chrome data is saved in: $USER_DATA_DIR"
