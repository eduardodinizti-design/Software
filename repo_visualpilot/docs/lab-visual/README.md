# Simulador visual — entrega de laboratório

## Para abrir a demonstração

1. Baixe `VisualPilot_Laboratorio.zip` desta pasta e escolha **Extrair tudo**.
2. Abra `VisualPilot_Laboratorio.html` com Chrome ou Edge.
3. Clique em **Iniciar simulação**.

Não requer Python, internet ou PowerShell. O arquivo reproduz execuções reais
gravadas do OCR e da política demonstrativa. É um replay interativo, não OCR
executado novamente no navegador.

Controles: iniciar/pausar, avançar uma etapa, reiniciar, ritmo, ocultar cartas,
ver imagem/leitura e exportar sessão JSON. O roteiro aplica Call, Check, Bet,
Raise e Fold nos botões da interface. Ocultar o Hero seleciona uma execução
gravada com a imagem realmente obstruída, sem substituir leitura por gabarito.

## Modo local com OCR ao vivo

No projeto com dependências instaladas, execute `INICIAR_LABORATORIO.bat` no
Windows, ou `python -m visualpilot.lab.server`. O servidor abre o navegador e
escuta somente 127.0.0.1:8765. O launcher Windows não foi executado neste Linux.

Cada captura roda `read_table`/RapidOCR, consulta `LaboratoryRangeBook` e retorna
uma decisão. Somente depois, a interface aciona o botão e envia `/api/apply`.
O atuador valida token da captura, mesa, geração, disponibilidade e sizing do
botão; rejeita duplicação e decisões antigas. Seus efeitos são exclusivamente
em memória no simulador. Não usa mouse do sistema, PPPoker, TCP do coletor,
Supabase nem comandos para outros programas.

O modo local salva PNGs originais e `events.jsonl` em `sessions/laboratory/`.
SHA-256 liga observação, decisão e ação à imagem. A versão portátil usa prévias
JPEG para reduzir o download; o hash continua sendo do PNG original.

## O que está sendo simulado

- Uma mesa cenográfica e cinco cenários roteirizados, não um motor completo de
  regras, distribuição aleatória, apostas legais, adversários ou cálculo de ganhos.
- As imagens do OCR são composições de capturas reais com patches e botões de
  teste. A mesa gráfica no navegador é uma representação didática; ela própria
  não é capturada pelo OCR. **Ver imagem e leitura** mostra a entrada efetiva.
- Cartas, board e botões passam pelo leitor real. Posição, stack efetivo, pote,
  histórico e pré-flop são fornecidos pelo cenário. A leitura óptica original
  (inclusive street desconhecida no pré-flop) é preservada no registro.
- A política `demo-1` demonstra o ciclo. Não é GTO nem range do trainer; não há
  treinamento automático, equivalência ao tracker ou expectativa de lucratividade.
- O exportador real do trainer ainda é necessário para substituir essa política.

## Validação executada

- Dez execuções para o HTML: cinco ações normais e cinco bloqueios por Hero oculto.
- Teste HTTP com OCR real: cinco ações, rejeição de token antigo, ação repetida,
  Hero oculto e persistência de seis imagens e diário.
- Chromium/Playwright: roteiro completo, fold visual, pausa/continuação,
  diálogo de evidência, download JSON, bloqueio com cartas ocultas e ação no
  servidor local. Zero erros JavaScript; sem overflow horizontal em largura 390.
- O navegador gerenciado bloqueou `file://`; a mesma versão portátil foi
  verificada por HTTP estático local. Abertura por duplo clique no Windows
  ainda não foi executada aqui.
- Suíte unificada: **176 testes em 95,388 s, sem falhas, três skips**.

Evidências: `targeted.log`, `full-suite.log` e `browser.json`.

## Reproduzir (desenvolvimento)

```bash
python -m tools.build_visual_lab --output dist/VisualPilot_Laboratorio.html
python -m visualpilot.lab.server --no-browser
# Outro terminal:
python -m http.server 8766 --bind 127.0.0.1 --directory dist
# Com Playwright e Chromium disponíveis:
python tools/check_visual_lab.py
```

O gerador preserva os dez PNGs e respectivos JSONs na pasta
`visual_lab_evidence` ao lado do HTML exportado.
