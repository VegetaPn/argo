# 设计笔记: X涨粉助手多源推文发现系统

## 问题分析

### 仅靠大V列表的局限性
1. **数量不足**: 大V发推频率有限（平均2-5条/天）
2. **时机问题**: 可能错过非大V的爆款推文
3. **覆盖面窄**: 只关注已知大V，错过新兴影响者
4. **竞争激烈**: 大V推文下评论众多，曝光机会小

### 理想的推文发现系统
- **数量充足**: 每小时至少10-20条候选推文
- **质量保证**: 有流行潜力，符合用户兴趣
- **时机精准**: 发布后5-15分钟内（早期评论曝光最高）
- **多样性**: 不同来源，降低风险

## 多源推文发现架构

### 来源1: 大V列表监控 (Managed Influencers)
```python
优先级: HIGH
频率: 每5分钟检查一次
配置: influencers/managed.json

流程:
1. 遍历managed influencers列表
2. 使用bird CLI获取每个用户的最新推文
3. 筛选出15分钟内的新推文
4. 自动进入候选池

bird命令:
- bird read @username --limit 5
- 解析JSON获取推文详情
```

### 来源2: 话题关键词搜索 (Topic Search)
```python
优先级: MEDIUM
频率: 每10分钟一轮
配置: config/search_topics.yaml

话题配置示例:
topics:
  - keywords: ["AI", "Claude", "LLM"]
    min_likes: 100
    max_age_minutes: 30
  - keywords: ["startup", "founder", "building"]
    min_likes: 50
    max_age_minutes: 20

流程:
1. 遍历配置的话题关键词
2. bird search "AI OR Claude" --min-likes 100
3. 过滤出30分钟内的推文
4. 计算相关性评分
5. 高分推文进入候选池

优势:
- 主动发现热门内容
- 不依赖大V列表
- 可灵活配置话题
```

### 来源3: 热门推文流 (Trending Stream)
```python
优先级: MEDIUM
频率: 每15分钟
方法: 搜索高互动推文

流程:
1. bird search "min_likes:500 min_retweets:50" --limit 50
2. 过滤出1小时内的推文
3. 排除已处理过的
4. 计算病毒式传播指数
5. 高潜力推文进入候选池

指标:
- 转发/点赞比例 (>0.3表示传播力强)
- 评论/点赞比例 (>0.1表示讨论度高)
- 时间衰减因子
```

### 来源4: 关注网络互动 (Following Network)
```python
优先级: LOW
频率: 每30分钟
方法: 分析你关注的人在互动什么

流程:
1. 获取你最近点赞/转发的推文
2. 分析这些推文的作者
3. 如果作者不在你的managed列表，获取其最新推文
4. 评估是否值得互动

优势:
- 发现你感兴趣的新账号
- 与你的兴趣自然对齐
- 扩展社交网络

bird命令:
- bird timeline --likes  # 获取你的点赞
- 解析作者信息
```

### 来源5: 智能推荐 (Smart Recommendations)
```python
优先级: LOW
频率: 每小时
方法: 基于历史成功数据推荐

流程:
1. 分析历史成功评论的特征
   - 推文话题、作者类型、互动水平
2. 构建推荐模型
3. 搜索符合模式的新推文
4. 推荐得分排序

机器学习特征:
- 作者粉丝数范围
- 推文长度、格式
- 发布时间段
- 话题分布
```

## 推文收集器实现

### 核心类设计
```python
class TweetCollector:
    def __init__(self):
        self.sources = [
            ManagedInfluencerSource(),
            TopicSearchSource(),
            TrendingStreamSource(),
            FollowingNetworkSource(),
            SmartRecommendationSource()
        ]

    async def collect_tweets(self) -> List[Tweet]:
        """并发从所有来源收集推文"""
        tasks = [source.fetch() for source in self.sources]
        results = await asyncio.gather(*tasks)
        tweets = self.merge_and_deduplicate(results)
        return self.filter_and_rank(tweets)

    def filter_and_rank(self, tweets):
        """过滤和排序"""
        # 1. 去重（同一推文从多个来源发现）
        # 2. 过滤已处理过的
        # 3. 按优先级和评分排序
        # 4. 返回Top 50
```

### 数据流
```
[5个来源并发采集]
    ↓
[合并去重] → 原始推文池 (100-200条/小时)
    ↓
[初步过滤]
  - 移除已评论的
  - 移除黑名单作者
  - 移除不相关话题
    ↓
[趋势分析] → 计算trending_score
    ↓
[评分排序] → Top 50候选推文
    ↓
[存储] → tweets/pending/
```

## 配置文件设计

### search_topics.yaml
```yaml
# 话题搜索配置
topics:
  - name: "AI和机器学习"
    keywords: ["AI", "LLM", "Claude", "ChatGPT", "machine learning"]
    min_likes: 100
    max_age_minutes: 30
    priority: high

  - name: "创业和产品"
    keywords: ["startup", "founder", "building", "launch", "product"]
    min_likes: 50
    max_age_minutes: 20
    priority: medium

  - name: "编程技术"
    keywords: ["Python", "JavaScript", "coding", "developer"]
    min_likes: 80
    max_age_minutes: 25
    priority: medium

# 搜索策略
search_strategy:
  enable_topic_search: true
  enable_trending_stream: true
  enable_network_analysis: true
  enable_smart_recommendations: false  # 初期关闭

  # 去重策略
  deduplication:
    time_window_hours: 24  # 24小时内不重复评论同一作者

  # 黑名单
  blacklist:
    authors: []  # 不想互动的账号
    keywords: ["政治", "争议"]  # 避免的关键词
```

### settings.yaml
```yaml
# 系统设置
collection:
  managed_influencers_interval: 5  # 分钟
  topic_search_interval: 10
  trending_stream_interval: 15
  network_analysis_interval: 30

  max_tweets_per_cycle: 50
  concurrent_sources: true

analysis:
  min_trending_score: 60  # 最低趋势分数
  early_bird_window_minutes: 15  # 最佳评论时间窗口

agent:
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 1024
  temperature: 0.7

notification:
  enable_desktop: true
  enable_terminal: true
  sound: true
```

## 预期效果

### 推文数量（每小时）
- 大V列表: 5-10条
- 话题搜索: 15-25条
- 热门推文流: 20-30条
- 关注网络: 5-10条
- 智能推荐: 10-15条
**总计: 55-90条候选推文/小时**

### 质量保证
- 多源交叉验证（同一推文被多个来源发现 → 高质量信号）
- 趋势分析过滤低质量推文
- 用户画像匹配度评分
- 最终呈现给用户：Top 10-20条/小时

## 下一步
1. 实现基础的TweetCollector框架
2. 先实现来源1和来源2（大V监控+话题搜索）
3. 集成bird CLI
4. 测试推文收集效果
