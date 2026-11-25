# Organizador por dentro — pesquisa IL2CPP do PPPoker

Objetivo: organizar as mesas do PPPoker de forma **robusta**, acionando o sistema
de janelas/tiling que o próprio cliente já tem por dentro, em vez de visão
computacional + arrasto de mouse (frágil, quebra a cada versão).

## Por que por dentro

O PPPoker (Unity/IL2CPP) desenha todas as mesas dentro de **uma janela Unity única**
(`UnityWndClass`, layered). As "janelas de mesa" com barra de título são objetos
desenhados, não janelas do Windows — então `SetWindowPos` externo não as alcança
uma a uma. Confirmado ao vivo na v228 (0 janelas-filho).

Mas o cliente tem, no código, o maquinário de organização pronto:
`MultiWindowManager`, `FloatingWindowController`, `MultiTableViewForPC`,
`CreateTableWindow`, `ApplyTile`, `DOTiling`, `CalcGridRects`. E o `GameAssembly.dll`
exporta 241 APIs `il2cpp_*` — dá para resolver qualquer classe/método **por nome**
(estável entre versões) e chamá-lo.

## Arquivos

- `recon.js` — **READ-ONLY**. Lista as classes/métodos de janela/mesa/tiling e seus
  endereços. Não chama nada, não altera estado. É seguro para observação.
- `run_recon.py` — anexa o Frida ao `PPPoker.exe` aberto e roda o `recon.js`;
  salva `recon_out.txt`.

## Como rodar (quando você decidir)

```powershell
# com o PPPoker aberto e 2-3 mesas na tela:
python research\ppp_il2cpp\run_recon.py
```

## AVISO de risco — leia antes

`frida.attach()` **instrumenta o processo** do PPPoker. Essa é a parte que um
anti-cheat pode detectar. Mesmo o recon read-only já faz attach. Portanto:

- Rode em **conta de teste / play money**, ou em conta/momento que você aceite o risco.
- NÃO rode durante um MTT valendo na conta principal.
- Observação passiva pura (sem Frida) — `enum_windows`, captura de tela — não injeta
  e é inofensiva; o recon já é um passo acima disso.

## Próximos passos (depois do recon)

1. Com o mapa de métodos do `recon_out.txt`, escrever `actions.js` (separado) que
   **chama** `ApplyTile`/`CreateTableWindow`/layout via `il2cpp_runtime_invoke` —
   primeiro em teste.
2. Decidir forma de produção: embarcar agente Frida no NVT Mesas, ou compilar uma
   DLL de injeção própria (precisa instalar Zig/clang — ainda ausente no PATH).
3. Integrar ao painel do NVT Mesas como "Organizar (modo interno)".
