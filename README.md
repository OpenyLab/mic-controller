# Gerenciador de Microfones (MicController)

Aplicativo desktop desenvolvido em **Python + PySide6** para **Windows 10 e Windows 11** que permite visualizar, ativar/desativar (mute/unmute), definir como padrão e ajustar o volume de cada interface de microfone individualmente em tempo real, utilizando diretamente a **Windows Core Audio API** (`MMDevice`, `IAudioEndpointVolume`, `IAudioMeterInformation` e `IPolicyConfig`).

---

## Funcionalidades Principais

1. **Listagem e Monitoramento em Tempo Real**
   - Detecta automaticamente todas as interfaces de captura de áudio (`EDataFlow.eCapture`).
   - Destaca o **Padrão do Sistema** (`eConsole`) e o **Padrão de Comunicação** (`eCommunications`).
   - Atualiza automaticamente a interface ao conectar ou desconectar microfones (`IMMNotificationClient` + sincronização assíncrona em `QThread`).
   - Opção para listar também dispositivos **desabilitados no Windows** ou com **cabo desconectado**, permitindo reabilitar endpoints desabilitados diretamente pelo aplicativo.

2. **Ativação e Desativação Individual**
   - Interruptor animado (`ToggleSwitch`) e botão de ação rápida em cada cartão para ativar (desmutar) ou desativar (silenciar) cada microfone sem afetar os demais.
   - Validação pós-operação diretamente no driver (`GetMute()`) para garantir que nenhuma alteração seja simulada.
   - Ações globais no cabeçalho e na bandeja para **Ativar Todos** ou **Desativar Todos** os microfones com um clique.

3. **Controle de Volume e Medidor de Sinal (VU Meter)**
   - Controle deslizante (`0%` a `100%`) com leitura numérica em porcentagem e ganho em decibéis (`dB`).
   - Botões rápidos de nível (`0%`, `25%`, `50%`, `75%`, `100%`).
   - Sincronização bidirecional com o Windows: alterações feitas pelo Painel de Som do Windows ou por botões físicos do headset refletem imediatamente nos cartões.
   - Barra de nível de entrada (`AudioLevelMeter`) em tempo real via `IAudioMeterInformation`.

4. **Integração com o Sistema Operacional**
   - **Bandeja do Sistema (`QSystemTrayIcon`)**: ícone dinâmico que muda de cor conforme o estado do microfone padrão (verde = ativo, vermelho = mudo), com menu rápido de ações.
   - **Inicialização com o Windows (`StartupManager`)**: configuração integrada ao Registro (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
   - **Atalho Global de Teclado (`GlobalHotkeyManager`)**: utiliza a API nativa Win32 (`RegisterHotKey`), permitindo alternar o microfone padrão de qualquer aplicativo ou jogo (padrão: `Ctrl+Shift+M`).

---

## Estrutura de Diretórios

```text
mic-controller/
├── __main__.py                  # Ponto de entrada principal (suporta `python .` ou `python __main__.py`)
├── main.py                      # Ponto de entrada da aplicação e CLI diagnóstico (`--list`, `--minimized`)
├── requirements.txt             # Dependências do projeto
├── README.md                    # Documentação completa e guia de solução de problemas
└── src/
    ├── __init__.py              # Metadados e versão do pacote
    ├── models/
    │   ├── __init__.py
    │   └── microphone.py        # Modelos de dados (MicrophoneDevice, DeviceHardwareState, OperationResult)
    ├── audio/
    │   ├── __init__.py
    │   ├── exceptions.py        # Exceções específicas de hardware, permissão e suporte
    │   ├── controller.py        # Integração Core Audio API (PyCAW / COM / IPolicyConfig / Meter)
    │   └── monitor.py           # Thread assíncrona (QThread + IMMNotificationClient)
    ├── services/
    │   ├── __init__.py
    │   ├── settings.py          # Persistência de configurações (QSettings)
    │   ├── startup.py           # Registro de inicialização automática no Windows (winreg)
    │   └── hotkeys.py           # Atalhos globais de teclado via Win32 RegisterHotKey
    └── ui/
        ├── __init__.py
        ├── styles.py            # Paletas de cores e temas Escuro / Claro (QSS)
        ├── icons.py             # Ícones vetoriais desenhados via QPainter (High-DPI)
        ├── main_window.py       # Janela principal, filtros, bandeja do sistema e orquestração
        └── widgets/
            ├── __init__.py
            ├── toggle_switch.py # Interruptor animado customizado
            ├── level_meter.py   # Medidor de nível de áudio em tempo real (VU Meter)
            ├── toast.py         # Notificações discretas flutuantes (ToastOverlay)
            ├── mic_card.py      # Cartão individual de cada microfone
            └── settings_dialog.py # Diálogo de configurações e utilitários do Windows
```

---

## Instalação e Execução

### 1. Pré-requisitos
- **Sistema Operacional:** Windows 10 ou Windows 11 (64 bits)
- **Python:** 3.10 ou superior

### 2. Criar e ativar o ambiente virtual (caso ainda não esteja ativo)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências
```powershell
pip install -r requirements.txt
```

### 4. Executar o aplicativo
```powershell
# Iniciar a interface gráfica normalmente
python __main__.py

# Ou iniciar diretamente minimizado na bandeja do sistema
python __main__.py --minimized

# Ou listar os microfones detectados no terminal (modo diagnóstico)
python __main__.py --list
```

---

## Gerar Executável (`.exe`) para Windows

O projeto inclui um script em Python ([`build_exe.py`](file:///d:/openylab/codigos/mic-controller/build_exe.py)), um script de lote ([`build.bat`](file:///d:/openylab/codigos/mic-controller/build.bat)) e a especificação otimizada do PyInstaller ([`MicController.spec`](file:///d:/openylab/codigos/mic-controller/MicController.spec)) que:
1. Gera automaticamente o ícone vetorial em alta resolução (`assets/app_icon.ico`);
2. Remove módulos pesados não utilizados do Qt (`WebEngine`, `Pdf`, `Qml`, `3D`) para reduzir o tamanho final;
3. Compila o aplicativo em um único executável standalone (`dist/MicController.exe`) sem janela de console preta.

### Opção 1 — Executar o script Python de build
```powershell
python build_exe.py --clean
```

### Opção 2 — Executar pelo arquivo `.bat` (duplo clique ou terminal)
```powershell
.\build.bat
```

### Opção 3 — Comando direto do PyInstaller
```powershell
pyinstaller --noconfirm --clean MicController.spec
```

Após a conclusão, o executável estará disponível em:
```text
dist/MicController.exe
```

---

## Solução de Problemas Comuns

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| **Microfone não aparece na lista principal** | O dispositivo está desabilitado no Painel de Som do Windows ou desconectado fisicamente. | Marque a caixa **"Mostrar desabilitados / desconectados"** na barra superior e clique em **"Habilitar no Windows"** no cartão do dispositivo, ou abra `mmsys.cpl` pelo menu **Configurações**. |
| **Erro de Permissão Negada (`0x80070005`)** | O acesso ao microfone está bloqueado nas configurações de privacidade do Windows. | Abra **Configurações** no aplicativo e clique em **"Privacidade do Microfone"** (`ms-settings:privacy-microphone`), habilitando o acesso para aplicativos desktop. |
| **Dispositivo desconectado durante o uso (`0x88890004`)** | Cabo USB/P2 removido ou reinicialização do driver de áudio (`AUDCLNT_E_DEVICE_INVALIDATED`). | O aplicativo captura a exceção automaticamente, exibe um aviso claro e atualiza a lista assim que o dispositivo é reconectado. |
| **Volume ou mute não altera em um driver virtual** | Alguns drivers virtuais de terceiros não implementam `IAudioEndpointVolume` completo. | O aplicativo lê de volta o valor real do driver após cada comando e informa explicitamente na interface caso o driver ignore ou limite a operação. |
| **Atalho global `Ctrl+Shift+M` não registra** | Outro programa em execução (ex.: Discord, navegador ou utilitário de placa de som) já reservou a mesma combinação no Windows. | Abra **⚙ Configurações** no aplicativo e escolha outra combinação de teclas (ex.: `Ctrl+Alt+M` ou `Ctrl+Shift+F9`). |

