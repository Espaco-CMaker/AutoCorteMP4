"""
AutoCorteMP4 v1.1.0
Projeto desktop para deteccao de cortes e exportacao de segmentos MP4.
Repositorio oficial: https://github.com/Espaco-CMaker/AutoCorteMP4
LLM utilizada no desenvolvimento: OpenAI GPT-5 (Codex)
"""

import os
import sys
from pathlib import Path

import yaml


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    # Required before importing PyQt6 in some systems.
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("AutoCorteMP4")
    app.setApplicationVersion("1.1.0")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    config = load_config()

    from gui.main_window import MainWindow

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
