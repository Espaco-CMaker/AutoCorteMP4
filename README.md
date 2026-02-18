# AutoCorteMP4

Versao atual: **v1.0.0**

Aplicativo desktop em Python para detectar cortes/transicoes em videos MP4 e exportar segmentos automaticamente.

Repositorio oficial: https://github.com/Espaco-CMaker/AutoCorteMP4

## Funcionalidades

- Interface grafica com PyQt6
- Analise de movimento por fluxo optico
- Deteccao de cortes por mudancas de cena
- Lista de cortes com timestamps e confianca
- Exportacao automatica de segmentos
- Processamento em threads para nao travar a UI

## Requisitos

- Python 3.14 (recomendado para este projeto)
- ffmpeg e ffprobe disponiveis no PATH

## Instalacao

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

## Execucao

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

- `v1.0.0`: primeira versao estavel publicada no GitHub.

## Licenca

MIT
