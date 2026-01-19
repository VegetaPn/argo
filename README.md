# Argo Growth - X/Twitter Growth Automation

通过评论大V推文来增长X粉丝的半自动化工具。

## 特性

- 🤖 使用 Claude Opus 4.5 生成个性化评论
- 📊 趋势分析：自动筛选热门推文
- ✋ 半自动模式：人工审核后发布
- 🎯 智能去重：避免重复评论同一作者
- 💾 轻量存储：JSON文件存储，无需数据库

## 前置要求

1. **bird CLI** - X/Twitter 命令行工具
   ```bash
   brew install steipete/tap/bird
   bird login
   ```

2. **Python 3.10+** 和依赖
   ```bash
   uv venv --python 3.12
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

3. **Claude API Key**
   ```bash
   export ANTHROPIC_API_KEY="your-api-key"
   ```

## 快速开始

### 1. 配置大V列表

编辑 `argo/growth/config/influencers.yaml`:

```yaml
influencers:
  - username: "example_user"
    priority: "high"
    check_interval: 15
    topics: ["AI", "Tech"]
```

### 2. 配置用户画像

编辑 `argo/growth/config/user_profile.yaml` 来定制你的评论风格。

### 3. 运行工作流

```bash
# 1. 检查认证
python main.py auth

# 2. 扫描推文并生成评论
python main.py scan

# 3. 审核评论（交互式）
python main.py review

# 4. 发布已批准的评论
python main.py publish

# 5. 查看统计
python main.py stats
```

## 命令说明

### `python main.py scan`
扫描大V推文，分析趋势，生成评论。

- 只收集最近30分钟的推文
- 按趋势评分排序
- 最多生成10条评论
- 评论保存为 `pending` 状态

### `python main.py review`
交互式审核待处理评论。

可用操作：
- `[p]` Publish now - 立即发布
- `[a]` Approve - 批准稍后发布
- `[r]` Refine - 优化评论（使用Agent会话记忆）
- `[s]` Skip - 跳过
- `[q]` Quit - 退出审核

### `python main.py publish`
批量发布所有已批准的评论。

### `python main.py stats`
显示统计信息：
- 评论状态分布
- 最近发布数量
- 大V列表

## 目录结构

```
argo/growth/
├── config/               # 配置文件
│   ├── user_profile.yaml  # 用户画像
│   ├── influencers.yaml   # 大V列表
│   └── settings.yaml      # 系统设置
├── core/                 # 核心模块
│   ├── bird_client.py     # bird CLI封装
│   ├── tweet_collector.py # 推文收集
│   ├── trend_analyzer.py  # 趋势分析
│   └── comment_generator.py # 评论生成
├── storage/              # 存储模块
│   ├── models.py          # 数据模型
│   └── file_store.py      # JSON存储
├── cli/                  # CLI模块
│   ├── main.py            # 主入口
│   └── reviewer.py        # 交互审核
└── data/                 # 数据目录
    ├── influencers/       # 大V数据
    ├── tweets/            # 推文（按日期）
    └── comments/          # 评论（按状态）
        ├── pending/
        ├── approved/
        ├── rejected/
        └── published/
```

## 工作原理

### 1. 推文收集
- 从配置的大V列表获取最新推文
- 过滤最近30分钟内的推文
- 去重：排除已处理的推文和最近24小时评论过的作者

### 2. 趋势分析
计算趋势评分（0-100）：
```
加权互动数 = 点赞×1.0 + 转发×2.0 + 评论×1.5
每分钟互动率 = 加权互动数 / 推文年龄（分钟）
趋势评分 = min(每分钟互动率 / 5 × 50, 100)
```

过滤规则：
- 默认阈值：40分
- 保护逻辑：至少保留3条推文

### 3. 评论生成
使用 Claude Agent SDK：
- 模型：Claude Opus 4.5
- 系统提示：注入用户画像和风格示例
- 会话记忆：支持多轮优化

### 4. 人工审核
交互式CLI：
- 显示推文上下文和互动数据
- 预览生成的评论
- 支持实时优化（使用会话上下文）
- 批准后立即发布或稍后批量发布

## 配置说明

### settings.yaml
```yaml
collection:
  max_tweet_age_minutes: 30    # 推文最大年龄
  max_tweets_per_scan: 10      # 每次扫描最多推文数

trend_analysis:
  min_score: 40.0              # 最低趋势评分
  like_weight: 1.0             # 点赞权重
  retweet_weight: 2.0          # 转发权重
  reply_weight: 1.5            # 评论权重

rate_limit:
  delay_seconds: 2.0           # bird CLI请求间隔
  max_concurrent_generations: 3 # 最大并发生成数
```

## 最佳实践

1. **认证管理**
   - 确保 `bird login` 认证正常
   - 定期运行 `python main.py auth` 检查状态

2. **评论风格**
   - 在 `user_profile.yaml` 中添加真实的评论示例
   - 风格保持一致：有梗但不失专业

3. **发布频率**
   - 避免短时间大量发布
   - 使用 `python main.py stats` 监控发布频率

4. **大V管理**
   - 根据质量调整 `priority` 和 `check_interval`
   - 定期review并更新大V列表

5. **趋势评分调优**
   - 根据实际效果调整 `min_score`
   - 调整权重以匹配你的目标人群

## 故障排查

### bird CLI认证失败
```bash
bird logout
bird login
```

### Claude API错误
检查API key和base URL：
```bash
echo $ANTHROPIC_API_KEY
echo $ANTHROPIC_BASE_URL  # 如果使用自定义endpoint
```

### 导入错误
确保在项目根目录运行：
```bash
cd /path/to/argo
python main.py scan
```

### 推文过滤过于严格
降低 `settings.yaml` 中的 `min_score`，或增加 `max_tweet_age_minutes`。

## 开发说明

### 导入规范
使用绝对导入：
```python
from argo.growth.storage.models import Tweet
from argo.growth.core.bird_client import BirdClient
```

### 运行测试
```bash
# TODO: 添加测试
pytest tests/
```

## License

MIT
