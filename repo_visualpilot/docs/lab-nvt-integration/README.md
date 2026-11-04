# Pré-flop NVT conectado ao simulador

O laboratório agora oferece cinco situações **pré-flop**, consultadas no pacote
real enviado pelo usuário, motor `ea758d9`. Não usa a política demo-1 nesse modo.

| Cenário | Cartas lidas | Contexto NVT | Resultado do pacote |
| --- | --- | --- | --- |
| 1 | 7d 3s | BB vs BTN, chip EV 25 BB | Fold 100% |
| 2 | 8h Jd | BB vs BTN, chip EV 25 BB | Call 100% |
| 3 | 5c 2s | BB vs BTN, chip EV 25 BB | Call 50% / Fold 50% |
| 4 | Kd Js | Abertura BTN, chip EV 25 BB | Raise 100%, execução bloqueada sem sizing |
| 5 | 8h Jd | BB contra limp, chip EV 25 BB | Check 100% |

As cartas e os botões passam por OCR real sobre imagens compostas de evidências
gravadas. O board permanece vazio. Posição, spot, stacks, fase e pré-flop vêm do
cenário controlado, não de reconhecimento automático desses campos. Os stacks
mostrados são os de `node.table` no exportador; a estratégia usa a mesa de
referência exportada, sem recalcular equilíbrio para novos stacks individuais.

## Misturas, sizings e escolhas manuais

- O painel mostra todas as frequências e o identificador/versão do nó consultado.
- Para demonstração automática, um sorteio ponderado usa uma semente fixa
  rastreável (hash do pacote + caso + lab-seed-42). Repetir o roteiro repete o
  resultado; não é uma nova amostra independente a cada execução.
- As frequências originais permanecem intactas. Apenas o sorteio normaliza somas
  com diferença de até 0,002 por arredondamento do exportador.
- Uma ação selecionada sem sizing **não é sorteada novamente** para cair em uma
  opção executável: ela fica bloqueada. Não há criação de raise/3bet/all-in sizes.
- O Call de 1 BB vem do cenário: abertura de 2 BB menos 1 BB já postado pelo BB.
  É o valor devido naquela mesa fictícia, não um sizing estratégico exportado.
- Em modo manual, **Avaliar minha escolha** consulta a correção NVT e mostra a
  perda de EV quando disponível. A avaliação não executa jogada.
- Clicar em Fold/Call/Check disponíveis aplica a ação na mesa fictícia e também
  registra sua avaliação. O motor aceita a intervenção humana mesmo se o range
  não recomenda a ação; o diário identifica o ator e a divergência.

## Duas formas de abrir

**Portátil:** extraia `VisualPilot_Preflop_NVT.zip`, abra o HTML e clique em
Iniciar simulação. Não requer Python. É replay interativo de consultas NVT/OCR
reais gravadas, com avaliações das escolhas disponíveis nesses cinco casos.
Não contém o pacote completo nem explora todos os 4.547 nós.

**OCR ao vivo:** com o ambiente do projeto instalado, coloque seu
`nvt-ranges-validados.json` na raiz e use `INICIAR_PREFLOP_NVT.bat`, ou:

```bash
python -m visualpilot.lab.server --nvt-ranges /caminho/nvt-ranges-validados.json
```

O launcher Windows ainda não foi testado fisicamente. O servidor e o navegador
foram testados em Linux. O servidor continua restrito a localhost.

## Validação desta entrega

- Cinco cenas, OCR real, consulta ao pacote, ação permitida ou bloqueio por sizing.
- Hero oculto impede consultar o range com as cartas do gabarito.
- Sorteio reproduzível e ponderado, sem modificar os mixes originais.
- Avaliação manual aceita Raise no cenário 4, mas não executa a aposta.
- Chromium: replay e servidor ao vivo, pausa/manual/retomada, mix visível,
  avaliação, oito adversários + Hero, diário, download e tela estreita.
- **187 testes executados em 109,415 s, sem falhas, três skips.**

Arquivos: `targeted.log`, `full-suite.log`, `browser.json`, sessões e screenshots.
Reproduzir o portátil:

```bash
python -m tools.build_visual_lab --nvt-ranges /caminho/nvt-ranges-validados.json --output dist/VisualPilot_Preflop_NVT.html
```

Ainda não é validação de captura de janelas Windows, de Wi-Fi, de contexto
pré-flop extraído automaticamente, de todos os nós na interface ou de execução
em cliente de poker. Nenhuma chamada de controle de mouse/teclado do sistema
foi adicionada. Pós-flop não participa desta integração estratégica.
