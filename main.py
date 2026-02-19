"""
AutoCorteMP4 v1.2.0
Projeto desktop para deteccao de cortes e exportacao de segmentos MP4.
Repositorio oficial: https://github.com/Espaco-CMaker/AutoCorteMP4
LLM utilizada no desenvolvimento: OpenAI GPT-5 (Codex)
"""

import os
import sys
from pathlib import Path

import yaml


def load_config(path: str = "config.yaml") -> dict:
    requested = Path(path)
    base_dir = Path(__file__).resolve().parent
    meipass_dir = Path(getattr(sys, "_MEIPASS", base_dir))

    candidates = []
    if requested.is_absolute():
        candidates.append(requested)
    else:
        candidates.extend([
            requested,
            Path.cwd() / requested,
            base_dir / requested,
            meipass_dir / requested,
        ])

    for config_path in candidates:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"config.yaml nao encontrado. Caminhos verificados: {searched}")


def main() -> None:
    # Required before importing PyQt6 in some systems.
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("AutoCorteMP4")
    app.setApplicationVersion("1.2.0")

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    config = load_config()

    from gui.main_window import MainWindow

    window = MainWindow(config)
    try:
        window.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        app.quit()


if __name__ == "__main__":
    main()
