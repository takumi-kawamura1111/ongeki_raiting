"""テスト。rating_manager/ で `python -m unittest` を実行すると全部走る

テスト対象のモジュールは src/ にあり、アプリと同じく `import rating` の形で読めるようにパスを通す
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
