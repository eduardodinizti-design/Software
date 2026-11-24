# Henrique — Instalação e Uso (notebook)

Agente da **Suprema Poker** que lê a(s) mesa(s) pela rede, **decide** pré e pós-flop, **clica** sozinho
e **salva as mãos** (H2N). Sobe por um atalho no Desktop com um **Wizard** gráfico — **sem console**.

---

## 1. Requisitos
- **Windows 10/11**.
- **Suprema Poker instalada** e logada (o Henrique anexa nela por rede, READ-ONLY).
- **Tesseract-OCR** instalado — o **anti-sit-out** lê o botão "Estou de volta" por OCR.
  Baixe: https://github.com/UB-Mannheim/tesseract/wiki (instale em `C:\Program Files\Tesseract-OCR`).
- As **ranges** do Henrique (`nvt-ranges-validados.json`, `nvt-ranges-deep.json`) — já vão no pacote; o
  instalador as coloca no lugar certo. **Sem elas o Henrique não decide o pré-flop.**

## 2. Instalação
1. Copie a pasta do pacote (que contém `Henrique\` + os scripts) para o notebook.
2. Clique com o botão direito em **`instalar.ps1`** → *Executar com PowerShell*
   (ou: `powershell -ExecutionPolicy Bypass -File instalar.ps1`).
3. O instalador: copia o app para `%LOCALAPPDATA%\NVT\Henrique`, coloca as **ranges** em
   `C:\Meus Projetos\Aplicativos\`, cria o atalho **"NVT Henrique"** no Desktop e checa o Tesseract.

> Para **gerar o pacote** a partir do código (na máquina de dev): rode `install\build.ps1`
> na raiz do repo — gera `dist\Henrique\`. Depois leve `dist\Henrique\` + `install\instalar.ps1`
> para o notebook e rode o instalador.

## 3. Como usar
1. **Abra a Suprema** e deixe **a(s) mesa(s) tiladas numa única janela** (1 a 4 colunas lado a lado).
   **Feche o Lobby** (Lobby aberto alarga a janela e erra a contagem de colunas).
2. Dê **duplo-clique no atalho "NVT Henrique"**. Sobe o **Wizard** (logo NVT), que anexa e sobe o agente.
3. No Wizard há a opção **"Armar — JOGAR sozinho"**:
   - **Desmarcado (padrão)** = DRY: ele lê, mostra o plano e salva as mãos, mas **não clica**.
   - **Marcado** = joga sozinho. O "Armar" é lido no **início** — marque e **reabra** para armar.
4. **Badge na tela** (faixa no topo) mostra o estado: **● ARMADO** (verde) / **● PAUSADO** (amarelo) /
   **● DESABILITADO** (vermelho), e a última ação por mesa.
5. **Atalhos globais** (a qualquer hora, de qualquer janela):
   - **Ctrl+Alt+R** = arma  ·  **Ctrl+Alt+P** = pausa (você assume as mesas)  ·  **Ctrl+Alt+D** = desliga limpo.
6. **Anti-sit-out:** se o Henrique ficar *sit-out*, ele detecta e clica **"Estou de volta"** sozinho
   (só quando ARMADO).
7. **Multi-mesa:** ele descobre qual mesa está em qual coluna **lendo o ID no feltro** (visão), então
   clica na mesa certa mesmo com 2/3/4 telas tiladas.

## 4. Parar / sair
- **Ctrl+Alt+D** (desliga limpo: desanexa o Frida sem travar o cliente), ou feche o Wizard (botão Parar).
- **Nunca** mate o processo "no tapa" — isso pode deixar um *hook* pendurado.

## 5. COMO ME MANDAR O LOG (pra eu avaliar a sessão)

O Henrique grava **tudo** da sessão: cada decisão, clique, mão salva, sit-out e o resumo final — além do
**stream cru de eventos** (o arquivo que eu uso pra reproduzir qualquer bug offline). Depois de jogar,
me mande esses logs:

**Jeito fácil (1 clique):**
1. Clique no atalho **"Coletar logs do Henrique"** no Desktop.
2. Ele junta os arquivos da última sessão numa pasta em **`Documentos\NVT_Henrique\sessao_<data_hora>\`**
   e **abre a pasta**.
3. **Anexe TODOS os arquivos dessa pasta aqui no chat.**

**Quais arquivos (se for pegar à mão):** em
`%LOCALAPPDATA%\NVT\Henrique\_internal\logs\` —
1. **`suprema_captura.log`** — o que ele decidiu/clicou/salvou (texto).
2. **`suprema_raw\suprema_<data>.jsonl`** — o **stream cru** (o MAIS importante; é com ele que eu
   reproduzo o bug sem te custar mesa).

> Dica: mande os **dois**. O `.jsonl` é o que permite eu achar a causa exata de um erro offline.

## 6. Problemas comuns
| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Badge "⚠ SEM DADOS" e ele para de agir | *hook mudo* (o Frida parou de receber) | **Feche e reabra a Suprema**, depois reabra o Henrique |
| "janela da Suprema não encontrada" | Suprema fechada/minimizada | Abra a Suprema numa mesa e reabra o atalho |
| Ele não clica "Estou de volta" no sit-out | Tesseract ausente | Instale o Tesseract-OCR (seção 1) |
| Nº de colunas errado / clica na mesa errada | Lobby aberto, ou janela redimensionando | Feche o Lobby; mantenha as mesas tiladas numa janela só |
| Windows Defender/antivírus bloqueia o .exe | Falso-positivo comum de apps PyInstaller | Libere a pasta `%LOCALAPPDATA%\NVT\Henrique` no antivírus |
| Silêncio por ~5 min perto da hora cheia | **break do torneio** (:55→:00) | Normal — não é bug; ele retoma sozinho |

## 7. Limitações honestas (estado atual)
- **Caminho fixo das ranges:** hoje o código carrega as ranges de `C:\Meus Projetos\Aplicativos\`
  (o instalador coloca lá). Portabilidade 100% (caminho relativo ao app) é um **follow-up** no código.
- **nvttracker (opcional):** a *re-validação* de saldo das mãos H2N usa um parser externo
  (`C:\Users\tacao\NvtVoz\nvttracker`). Sem ele, o Henrique **ainda salva** as mãos, só não re-valida.
- **Tesseract externo:** precisa estar instalado (não vai embutido no .exe).
- **Pós-flop e multi-mesa armado** estão em **homologação** — valide em sessões curtas antes de longas.
