# AI日报 - 定时任务配置
# 每天早上9点自动推送新资讯

## 方法一：Crontab (Linux/Mac)

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天早上9点执行）
0 9 * * * cd ~/ai-daily-v2 && python3 scraper/push_daily.py >> logs/push.log 2>&1

# 每小时检查一次更新
0 * * * * cd ~/ai-daily-v2 && python3 scraper/scraper.py >> logs/scraper.log 2>&1
```

## 方法二：Systemd Timer (Linux)

创建文件 `/etc/systemd/system/ai-daily-push.service`:
```ini
[Unit]
Description=AI Daily Push Service

[Service]
Type=oneshot
WorkingDirectory=/home/user/ai-daily-v2
ExecStart=/usr/bin/python3 scraper/push_daily.py
User=user
```

创建文件 `/etc/systemd/system/ai-daily-push.timer`:
```ini
[Unit]
Description=Run AI Daily Push every day at 9:00

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

启用定时器:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-daily-push.timer
sudo systemctl start ai-daily-push.timer
```

## 方法三：GitHub Actions (推荐)

创建文件 `.github/workflows/daily-push.yml`:
```yaml
name: Daily Push

on:
  schedule:
    - cron: '0 1 * * *'  # UTC 01:00 = 北京时间 09:00
  workflow_dispatch:

jobs:
  push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Run push script
        run: python scraper/push_daily.py
      
      - name: Send notification
        uses: lizheming/drone-wechat@master
        with:
          webhook: ${{ secrets.WEBHOOK_URL }}
          content: ${{ steps.push.outputs.message }}
```

## 方法四：Vercel Cron (Serverless)

配置 `vercel.json`:
```json
{
  "crons": [
    {
      "path": "/api/push",
      "schedule": "0 1 * * *"
    }
  ]
}
```

## 推送消息格式

生成的推送消息示例：

```
📰 AI日报 - 2026-03-03

📊 24小时新增: 42 条
🔥 突发新闻: 5 条

📌 重要资讯:
1. OpenAI完成1100亿美元融资，估值达8400亿...
   📈 相关: MSFT, AMZN, NVDA
2. Meta与AMD达成600-1000亿美元超级采购协议...
   📈 相关: META, AMD
3. 英伟达Q4营收681亿美元暴增73%...
   📈 相关: NVDA

🔗 查看详情: https://bianchunshan.github.io/ai-daily-v2/
```

## 测试推送

手动执行测试:
```bash
cd ~/ai-daily-v2
python3 scraper/push_daily.py
```

## 查看日志

```bash
# 创建日志目录
mkdir -p logs

# 查看推送日志
tail -f logs/push.log

# 查看采集日志
tail -f logs/scraper.log
```