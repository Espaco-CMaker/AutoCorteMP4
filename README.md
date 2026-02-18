# AutoCorteMP4

Versão atual: **v1.1.1**

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

| Tecnologia | Versão | Para que foi usada |
|---|---|---|
| Python | 3.14 | Linguagem principal da aplicação desktop. |
| PyQt6 | >= 6.5.0 | Interface gráfica (janela principal, controles, eventos e sinais/slots). |
| PyQt6-Qt6 | >= 6.5.0 | Runtime Qt usado pelo PyQt6 para renderização da UI. |
| opencv-python | >= 4.8.0 | Leitura de vídeo e processamento de frames (incluindo fluxo óptico). |
| scikit-image | >= 0.21.0 | Métricas de análise de imagem para apoio na detecção de cortes. |
| NumPy | >= 1.24.0 | Operações numéricas e manipulação eficiente de arrays dos frames. |
| SciPy | (dependência do scikit-image) | Rotinas numéricas usadas indiretamente na análise de imagem. |
| pyqtgraph | >= 0.13.3 | Visualização em tempo real dos vetores e métricas da análise. |
| ffmpeg-python | >= 0.2.0 | Integração Python para cortar/exportar segmentos de vídeo. |
| ffmpeg / ffprobe | ferramenta de sistema (PATH) | Processamento e inspeção de mídia no nível do sistema. |
| PyYAML | >= 6.0 | Leitura de configurações do projeto (`config.yaml`). |
| tqdm | >= 4.65.0 | Feedback de progresso em etapas de processamento. |
| Pillow | >= 10.0.0 | Geração/manipulação de imagens auxiliares (ex.: thumbnails). |

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

- `v1.1.1`: política de versionamento/changelog formalizada e documentação de release.
- `v1.1.0`: versão estável e operacional.
- `v1.0.0`: primeira versão estável publicada no GitHub.

## Política de Versionamento e Changelog

- Padrão de versão: `X.Y.Z`
- Incrementar `Z` para cada correção/ajuste local (bugfix, texto, refino, melhoria pontual).
- Incrementar `Y` para cada versão publicada no GitHub (release).
- Atualizar sempre, no mesmo submit:
  - cabeçalho de versão em `main.py`
  - versão atual neste `README.md`
  - registro da mudança em `CHANGELOG.md`
  - mensagem de commit com resumo objetivo do que foi modificado

### Padrão sugerido de commit (submit)

```text
type(scope): vX.Y.Z - resumo curto

- item 1 do que foi alterado
- item 2 do que foi alterado
- item 3 do que foi alterado
```

## Licença

MIT
