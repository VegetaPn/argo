"""CLI命令入口"""

import asyncio
import yaml
from pathlib import Path
from typing import Optional
from datetime import datetime
import argparse

from argo.growth.core.bird_client import BirdClient, BirdClientError
from argo.growth.core.tweet_collector import TweetCollector
from argo.growth.core.trend_analyzer import TrendAnalyzer
from argo.growth.core.comment_generator import CommentGenerator
from argo.growth.storage.file_store import FileStore
from argo.growth.storage.models import Influencer
from argo.growth.cli.reviewer import run_review


class ArgoGrowth:
    """Argo Growth CLI主程序"""

    def __init__(self, config_dir: Optional[Path] = None, data_dir: Optional[Path] = None):
        # 默认路径
        self.config_dir = config_dir or Path.cwd() / "argo" / "growth" / "config"
        self.data_dir = data_dir or Path.cwd() / "argo" / "growth" / "data"

        # 加载配置
        self.user_profile = self._load_yaml(self.config_dir / "user_profile.yaml")
        self.settings = self._load_yaml(self.config_dir / "settings.yaml")

        # 初始化组件
        self.store = FileStore(self.data_dir)
        self._init_influencers_from_config()  # 从配置初始化influencers
        self.bird = BirdClient(delay=self.settings['rate_limit']['delay_seconds'])
        self.collector = TweetCollector(self.bird, self.store)
        self.analyzer = TrendAnalyzer(
            like_weight=self.settings['trend_analysis']['like_weight'],
            retweet_weight=self.settings['trend_analysis']['retweet_weight'],
            reply_weight=self.settings['trend_analysis']['reply_weight']
        )
        self.generator = CommentGenerator(self.user_profile)

    def _load_yaml(self, path: Path) -> dict:
        """加载YAML配置"""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _init_influencers_from_config(self):
        """从配置文件初始化influencers到数据存储"""
        config_file = self.config_dir / "influencers.yaml"

        # 如果配置文件不存在，跳过
        if not config_file.exists():
            return

        managed_file = self.data_dir / "influencers" / "managed.json"

        # 检查是否需要重新加载
        should_reload = False

        if not managed_file.exists():
            # managed.json不存在，需要加载
            should_reload = True
        else:
            # 比较修改时间，如果YAML比managed.json新，重新加载
            config_mtime = config_file.stat().st_mtime
            managed_mtime = managed_file.stat().st_mtime

            if config_mtime > managed_mtime:
                print(f"⚠️  influencers.yaml has been modified, reloading...")
                should_reload = True

        if not should_reload:
            return

        # 从YAML加载配置
        config = self._load_yaml(config_file)
        influencers_data = config.get('influencers', [])

        if not influencers_data:
            return

        # 转换为Influencer对象
        influencers = []
        for item in influencers_data:
            influencer = Influencer(
                username=item['username'],
                user_id=item.get('user_id', ''),
                priority=item.get('priority', 'medium'),
                check_interval=item.get('check_interval', 15),
                topics=item.get('topics', []),
                notes=item.get('notes', ''),
                added_at=datetime.now()
            )
            influencers.append(influencer)

        # 保存到managed.json
        self.store.save_influencers(influencers)
        print(f"✅ Loaded {len(influencers)} influencer(s) from config")

    def check_auth(self):
        """检查bird CLI认证状态"""
        print("🔐 Checking bird CLI authentication...")
        success, result = self.bird.check_auth()

        if success:
            print(f"✅ Authenticated as @{result}")
            return True
        else:
            print(f"❌ Authentication failed: {result}")
            print("\nPlease authenticate with: bird login")
            return False

    async def scan_and_generate(self):
        """扫描推文并生成评论"""
        print("\n🚀 Starting tweet scan and comment generation...")
        print("=" * 80)

        # 1. 加载大V列表
        influencers = self.store.load_influencers()
        if not influencers:
            print("⚠️  No influencers configured")
            print(f"Please add influencers to: {self.config_dir / 'influencers.yaml'}")
            return

        print(f"📋 Loaded {len(influencers)} influencer(s)")

        # 2. 收集推文
        print("\n📡 Collecting tweets...")
        max_age = self.settings['collection']['max_tweet_age_minutes']
        tweets = self.collector.collect_from_influencers(influencers, max_age_minutes=max_age)

        if not tweets:
            print("📭 No new tweets found")
            return

        print(f"✅ Collected {len(tweets)} new tweet(s)")

        # 3. 趋势分析
        print("\n📈 Analyzing trends...")
        min_score = self.settings['trend_analysis']['min_score']
        max_tweets = self.settings['collection']['max_tweets_per_scan']

        ranked = self.analyzer.rank_tweets(
            tweets,
            min_score=min_score,
            min_tweets=3
        )

        # 限制数量
        ranked = ranked[:max_tweets]

        print(f"🎯 Selected {len(ranked)} trending tweet(s)")
        for i, tweet in enumerate(ranked, 1):
            print(f"   {i}. @{tweet.author.username}: {tweet.trending_score}/100")

        # 4. 生成评论
        print("\n🤖 Generating comments...")
        comments = await self.generator.generate_batch(
            ranked,
            max_concurrent=self.settings['rate_limit']['max_concurrent_generations']
        )

        # 5. 保存评论
        for comment in comments:
            self.store.save_comment(comment)

        print(f"\n✅ Generated {len(comments)} comment(s)")
        print("=" * 80)

        # 6. 显示统计
        stats = self.store.get_comment_stats()
        print("\n📊 Comment Stats:")
        print(f"   Pending: {stats['pending']}")
        print(f"   Approved: {stats['approved']}")
        print(f"   Published: {stats['published']}")
        print(f"   Rejected: {stats['rejected']}")

    def review_comments(self):
        """审核评论"""
        print("\n📝 Starting comment review...")
        run_review(self.store, self.bird, self.generator)

    def publish_approved(self):
        """发布已批准的评论"""
        print("\n🚀 Publishing approved comments...")
        approved = self.store.load_comments_by_status('approved')

        if not approved:
            print("📭 No approved comments to publish")
            return

        print(f"Found {len(approved)} approved comment(s)")

        success_count = 0
        for i, comment in enumerate(approved, 1):
            print(f"\n[{i}/{len(approved)}] Publishing comment {comment.id[:8]}...")

            if self.bird.post_reply(comment.tweet_id, comment.content):
                self.store.update_comment_status(comment.id, 'published')
                success_count += 1
                print("   ✅ Published")
            else:
                print("   ❌ Failed")

        print(f"\n✅ Successfully published {success_count}/{len(approved)} comment(s)")

    def show_stats(self):
        """显示统计信息"""
        print("\n📊 Argo Growth Statistics")
        print("=" * 80)

        # 评论统计
        stats = self.store.get_comment_stats()
        print("\n💬 Comments:")
        print(f"   Pending:   {stats['pending']}")
        print(f"   Approved:  {stats['approved']}")
        print(f"   Published: {stats['published']}")
        print(f"   Rejected:  {stats['rejected']}")

        # 最近发布
        recent_1h = self.store.get_recent_published_count(hours=1)
        recent_24h = self.store.get_recent_published_count(hours=24)
        print(f"\n📈 Recent Activity:")
        print(f"   Last 1 hour:  {recent_1h} published")
        print(f"   Last 24 hours: {recent_24h} published")

        # 大V列表
        influencers = self.store.load_influencers()
        print(f"\n👥 Influencers: {len(influencers)}")

        print("=" * 80)


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(
        description='Argo Growth - X/Twitter Growth Automation'
    )

    parser.add_argument(
        'command',
        choices=['scan', 'review', 'publish', 'stats', 'auth'],
        help='Command to run'
    )

    parser.add_argument(
        '--config-dir',
        type=Path,
        help='Configuration directory (default: ./argo/growth/config)'
    )

    parser.add_argument(
        '--data-dir',
        type=Path,
        help='Data storage directory (default: ./argo/growth/data)'
    )

    args = parser.parse_args()

    try:
        app = ArgoGrowth(config_dir=args.config_dir, data_dir=args.data_dir)

        if args.command == 'auth':
            app.check_auth()

        elif args.command == 'scan':
            if not app.check_auth():
                return
            asyncio.run(app.scan_and_generate())

        elif args.command == 'review':
            if not app.check_auth():
                return
            app.review_comments()

        elif args.command == 'publish':
            if not app.check_auth():
                return
            app.publish_approved()

        elif args.command == 'stats':
            app.show_stats()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except BirdClientError as e:
        print(f"❌ Bird CLI Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
