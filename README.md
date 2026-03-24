# Piano Score Generator 🎹

输入歌曲名字，自动产出简单、中等、难三种难度的钢琴乐谱，并自动设计乐谱指法，最终输出 PDF。

## 功能特性

- **MIDI 解析**: 使用 music21 解析 MIDI 文件，提取音符、调性、拍号、速度等信息
- **智能改编**: 自动生成简单、中等、难三种难度的钢琴改编谱
- **自动指法**: 基于规则引擎自动标注合理指法（1-5 指）
- **多源 MIDI 获取**: 支持本地文件、Web 爬虫、Midishow 中文 MIDI 库
- **PDF 输出**: 支持通过 MuseScore CLI 渲染高质量 PDF 乐谱
- **REST API**: 提供 FastAPI 接口，便于前端扩展

## 安装

```bash
pip install -r requirements.txt
```

### MIDI 数据源

本项目支持多种 MIDI 文件获取方式：

| 数据源 | 说明 | 需要登录 |
|--------|------|:--------:|
| 本地文件 | 从 `samples/` 目录加载 | ❌ |
| Web 爬虫 | 从 freemidi.org / mididb.com / midiworld.com 搜索下载 | ❌ |
| **Midishow** | 中文 MIDI 库，中文流行歌曲最全 | ✅ 需要注册+积分 |

#### Midishow 配置

Midishow 是中文 MIDI 音乐分享网站，注册送 5 积分（每首歌 3 积分）。

```bash
# 方式一：环境变量
export MIDISHOW_USERNAME="你的用户名"
export MIDISHOW_PASSWORD="你的密码"

# 方式二：代码中设置
from backend.midi_fetcher import MidishowFetcher
fetcher = MidishowFetcher(username="xxx", password="xxx")
```

### 可选依赖

- **MuseScore 4**: 用于渲染高质量 PDF。安装后确保 `mscore` 命令可用。
  - macOS: `brew install --cask musescore`
  - 若未安装，程序将输出 MusicXML 文件。
- **Playwright**: 用于浏览器自动化（Midishow 动态加载场景，可选）
  ```bash
  pip install playwright
  playwright install chromium
  ```

## 使用方式

### 命令行

```bash
# 使用本地 MIDI 文件
python run.py --song "这世界那么多人" --output ./output

# 指定 MIDI 文件
python run.py --song "这世界那么多人" --midi ./samples/song.mid --output ./output

# 指定难度（可选: easy, medium, hard, all）
python run.py --song "这世界那么多人" --difficulty all --output ./output
```

### API 服务

```bash
# 启动 API 服务
python run.py --serve

# 调用接口
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"song_name": "这世界那么多人"}'
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 输入歌曲名，生成三种难度乐谱 |
| GET | `/api/scores/{id}` | 获取乐谱详情 |
| GET | `/api/scores/{id}/pdf` | 下载 PDF |
| GET | `/api/health` | 健康检查 |

## 项目结构

```
piano-score-gen/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── midi_fetcher/        # MIDI 文件获取
│   │   ├── base.py          #   抽象基类
│   │   ├── local.py         #   本地文件加载
│   │   ├── downloader.py    #   Web 爬虫（freemidi/mididb/midiworld）
│   │   └── midishow.py      #   Midishow 中文 MIDI 库
│   ├── parser/              # MIDI 解析
│   ├── arranger/            # 改编引擎（简单/中等/难）
│   ├── fingering/           # 指法引擎
│   ├── renderer/            # 渲染输出（MuseScore/MusicXML）
│   ├── models/              # 数据模型
│   └── api/                 # API 路由
├── output/                  # 输出目录
├── samples/                 # 示例 MIDI 文件
└── run.py                   # 启动脚本
```

## 技术栈

- Python 3.10+
- music21 (MIDI 解析与乐谱操作)
- FastAPI (REST API)
- MuseScore (PDF 渲染)
- Pydantic (数据验证)
