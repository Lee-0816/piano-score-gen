"""Piano Score Generator - 启动脚本

命令行模式：
    python run.py --song "这世界那么多人" --output ./output

API 服务模式：
    python run.py --serve

Usage:
    python run.py [OPTIONS]

Options:
    --song TEXT         歌曲名称（必填，除非 --serve）
    --midi PATH        指定本地 MIDI 文件路径
    --difficulty TEXT  难度选择：easy, medium, hard, all（默认 all）
    --output PATH     输出目录（默认 ./output）
    --serve           启动 API 服务模式
    --host TEXT       API 服务地址（默认 0.0.0.0）
    --port INT        API 服务端口（默认 8000）
"""

import argparse
import sys
from pathlib import Path

from backend.parser.midi_parser import MidiParser
from backend.midi_fetcher.local import LocalMidiFetcher
from backend.midi_fetcher.downloader import WebMidiFetcher
from backend.arranger.easy import EasyArranger
from backend.arranger.medium import MediumArranger
from backend.arranger.hard import HardArranger
from backend.renderer.musescore import MuseScoreRenderer
from backend.models.score import DifficultyLevel


def get_midi_file(song_name: str, midi_path: str = None) -> Path:
    """获取 MIDI 文件。
    
    按优先级：指定路径 > 本地搜索 > 网上下载
    
    Args:
        song_name: 歌曲名称
        midi_path: 指定的 MIDI 文件路径
        
    Returns:
        MIDI 文件路径
        
    Raises:
        FileNotFoundError: 找不到 MIDI 文件
    """
    # 1. 如果指定了路径，直接使用
    if midi_path:
        path = Path(midi_path)
        if path.exists():
            print(f"✅ 使用指定的 MIDI 文件: {path}")
            return path
        else:
            raise FileNotFoundError(f"指定的 MIDI 文件不存在: {path}")

    # 2. 本地搜索
    print(f"🔍 在本地搜索 MIDI 文件: {song_name}")
    local_fetcher = LocalMidiFetcher()
    midi_file = local_fetcher.fetch(song_name)
    if midi_file:
        print(f"✅ 找到本地 MIDI 文件: {midi_file}")
        return midi_file

    # 3. 网上下载
    print(f"🌐 尝试从网上下载 MIDI 文件: {song_name}")
    web_fetcher = WebMidiFetcher()
    midi_file = web_fetcher.fetch(song_name)
    if midi_file:
        print(f"✅ 成功下载 MIDI 文件: {midi_file}")
        return midi_file

    raise FileNotFoundError(
        f"❌ 未找到歌曲 \"{song_name}\" 的 MIDI 文件。\n"
        f"请将 MIDI 文件放到 samples/ 目录下，或使用 --midi 参数指定文件路径。"
    )


def run_generate(args):
    """执行乐谱生成。
    
    Args:
        args: 命令行参数
    """
    song_name = args.song
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"🎹 Piano Score Generator")
    print(f"{'='*50}")
    print(f"歌曲: {song_name}")
    print(f"难度: {args.difficulty}")
    print(f"输出: {output_dir}")
    print(f"{'='*50}\n")

    # 1. 获取 MIDI 文件
    try:
        midi_path = None
        # 优先从 URL 下载
        if args.url:
            print(f"🌐 从 URL 下载 MIDI: {args.url}")
            fetcher = WebMidiFetcher()
            midi_path = fetcher.download_from_url(args.url, song_name)
            if not midi_path:
                raise FileNotFoundError(f"从 URL 下载失败: {args.url}")
        # 其次用本地文件
        elif args.midi:
            midi_path = Path(args.midi)
            if not midi_path.exists():
                raise FileNotFoundError(f"指定的 MIDI 文件不存在: {midi_path}")
        # 最后自动搜索
        else:
            midi_path = get_midi_file(song_name)
            
        print(f"✅ MIDI 文件: {midi_path}")
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    # 2. 解析 MIDI
    print("📖 解析 MIDI 文件...")
    parser = MidiParser()
    try:
        score = parser.parse(midi_path, title=song_name)
        print(f"   调性: {score.key}")
        print(f"   拍号: {score.time_signature}")
        print(f"   速度: {score.tempo} BPM")
        print(f"   声部数: {len(score.parts)}")
    except Exception as e:
        print(f"❌ MIDI 解析失败: {e}")
        sys.exit(1)

    # 3. 确定要生成的难度
    if args.difficulty == "all":
        difficulties = [
            DifficultyLevel.EASY,
            DifficultyLevel.MEDIUM,
            DifficultyLevel.HARD,
        ]
    else:
        difficulties = [DifficultyLevel(args.difficulty)]

    # 4. 初始化改编器和渲染器
    arrangers = {
        DifficultyLevel.EASY: EasyArranger(),
        DifficultyLevel.MEDIUM: MediumArranger(),
        DifficultyLevel.HARD: HardArranger(),
    }
    renderer = MuseScoreRenderer()

    if not renderer.has_musescore:
        print("⚠️  MuseScore 未安装，将只输出 MusicXML 文件。")
        print("   安装 MuseScore 可生成 PDF: https://musescore.org/\n")

    # 5. 生成各难度乐谱
    for diff in difficulties:
        print(f"🎵 生成{diff.value}版乐谱...")
        arranger = arrangers[diff]

        try:
            arrangement = arranger.arrange(score)
            results = renderer.render(arrangement, output_dir=output_dir)

            for fmt, path in results.items():
                print(f"   ✅ {fmt.upper()}: {path}")

        except Exception as e:
            print(f"   ❌ 生成失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"🎉 完成！输出目录: {output_dir}")
    print(f"{'='*50}")


def run_server(args):
    """启动 API 服务。
    
    Args:
        args: 命令行参数
    """
    import uvicorn
    from backend.config import API_HOST, API_PORT

    host = args.host or API_HOST
    port = args.port or API_PORT

    print(f"\n🎹 启动 Piano Score Generator API 服务")
    print(f"   地址: http://{host}:{port}")
    print(f"   文档: http://{host}:{port}/docs\n")

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
    )


def main():
    """主入口函数。"""
    parser = argparse.ArgumentParser(
        description="Piano Score Generator - 输入歌曲名，生成钢琴乐谱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py --song "这世界那么多人"
  python run.py --song "这世界那么多人" --midi ./song.mid
  python run.py --song "这世界那么多人" --difficulty easy
  python run.py --serve
        """,
    )

    parser.add_argument("--song", type=str, help="歌曲名称")
    parser.add_argument("--midi", type=str, help="指定本地 MIDI 文件路径")
    parser.add_argument("--url", type=str, help="指定 MIDI 文件的直接下载 URL")
    parser.add_argument(
        "--difficulty",
        type=str,
        default="all",
        choices=["easy", "medium", "hard", "all"],
        help="难度选择 (默认: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./output",
        help="输出目录 (默认: ./output)",
    )
    parser.add_argument("--serve", action="store_true", help="启动 API 服务")
    parser.add_argument("--host", type=str, help="API 服务地址")
    parser.add_argument("--port", type=int, help="API 服务端口")

    args = parser.parse_args()

    if args.serve:
        run_server(args)
    elif args.song:
        run_generate(args)
    else:
        parser.print_help()
        print("\n❌ 请指定 --song 参数或使用 --serve 启动服务。")
        sys.exit(1)


if __name__ == "__main__":
    main()
