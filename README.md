# AutoCorteMP4

Versão atual: **v1.1.0**

Aplicativo desktop em Python para detectar cortes/transições em vídeos MP4 e exportar segmentos automaticamente.

Repositório oficial: https://github.com/Espaco-CMaker/AutoCorteMP4

LLM utilizada no desenvolvimento: **OpenAI GPT-5 (Codex)**

## Funcionalidades

- Interface gráfica com PyQt6
- Análise de movimento por fluxo óptico
- Detecção de cortes por mudanças de cena
- Lista de cortes com timestamps e confiança
- Exportação automática de segmentos
- Processamento em threads para não travar a UI

## Tecnologias Utilizadas

- Linguagem: `Python 3.14`
- Interface gráfica: `PyQt6` e `PyQt6-Qt6`
- Visão computacional: `OpenCV (opencv-python)` e `scikit-image`
- Cálculo numérico: `NumPy` e `SciPy`
- Gráficos: `pyqtgraph`
- Manipulação de vídeo: `ffmpeg-python` (com `ffmpeg`/`ffprobe` instalados no sistema)
- Configuração e utilitários: `PyYAML`, `tqdm`, `Pillow`

## Requisitos

- Python 3.14 (recomendado para este projeto)
- ffmpeg e ffprobe disponíveis no PATH

## O Que Precisa Instalar

1. Python 3.14
2. ffmpeg (inclui `ffprobe`) no PATH do sistema
3. Dependências Python do projeto:
   - instaladas com `pip install -r requirements.txt`

## Instalação

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Execução

```bash
.venv\\Scripts\\python.exe main.py
```

## Estrutura do projeto

```text
AutocorteMP4/
|- main.py
|- config.yaml
|- requirements.txt
|- analyzer/
|- exporter/
|- gui/
```

## Versionamento

- `v1.1.0`: versão estável e operacional.
- `v1.0.0`: primeira versão estável publicada no GitHub.

## Licença

MIT
