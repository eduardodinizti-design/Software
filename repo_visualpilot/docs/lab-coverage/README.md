# Auditoria ampliada de uma mesa — 29/10/2026

Suíte final: **173 testes executados em 85,158 s, sem falhas, três skips**.
Log integral em `full-suite.log`; sete verificações direcionadas em `targeted.log`.
Nos três reinícios integrados do coletor, leituras completas em 1,707 / 1,526 /
1,920 s. São medições locais, não garantia de desempenho em Wi-Fi ou Windows.

## Evidência por tela

Execute `.venv/bin/python -m tools.audit_single_table --output docs/lab-coverage`.
`report.json` guarda arquivo, SHA-256, gabarito, leitura, caixas de evidência,
diagnósticos e tempo. `index.md` liga cada caso à sua imagem de origem.
`cards.md` mostra a cobertura das 52 cartas, separando Hero real, board real e
turn sintético; o JSON identifica também cada posição observada.
Espaços removidos pelo OCR são normalizados na comparação textual; números
não são arredondados ou substituídos para aprovar o caso.

Resultado: **46 casos aprovados, zero divergências, quatro arquivos ausentes**.
São dez frames reais e 36 imagens sintéticas em board_turn. Os reais cobrem
16 cartas distintas (10 no Hero e 8 no board, com sobreposição), não todas as
52 cartas em todos os lugares. As quatro ausências são 145_0, 145_1, 158_0 e
158_1. Ausência de board não aprova pré-flop: continua desconhecido.

## Botões e valores

Adicionado `hero_buttons` estruturado com ação, valor, unidade, texto original,
confiança e caixa da leitura. Preservado `actions` para compatibilidade.
Valor ilegível fica pendente; alteração da região invalida também o novo campo.
Em right_99: Fold, Call 2,5 BB e Raise; cinco ações de jogadores ficam separadas.
Pote e stack dos dois frames de ações conferidos contra leitura visual manual.

Cinco rótulos (fold/check/call/bet/raise) e exemplos de valores passaram com OCR
real sobre recortes de texto sintético. Isso valida o leitor em texto localizado,
não todos os botões reais do cliente. Inicialmente o teste passava uma faixa com
grandes margens a `field()`; foi ajustado para o contrato de recorte de texto.
Não houve redução do limiar de confiança para aceitar texto incompleto.

## Reiniciar o coletor

Após mais de cinco segundos sem pacote aceito do membro, outra sessão desse
membro substitui a anterior. Identidades antigas são retiradas da fila, do
runtime e do painel; os registros históricos permanecem separados por sessão.
Pacotes atrasados de sessões retiradas são rejeitados. Uma segunda instância não
assume enquanto a primeira continua enviando. Isso não implementa autenticação.

Teste de oito substituições verifica liberação do limite e reutilização de Mesa 1.
Teste integrado usa três sessões novas, TCP e OCR reais, verificando uma mesa
visível por vez, diário separado por identidade e sequência correta das cartas.
Mesmo ID de membro é obrigatório para reconhecer a substituição.

## Cobertura ainda pendente

| Objetivo | Situação |
| --- | --- |
| Flop, turn e river | Exemplos reais conferidos; sequência integrada também coberta |
| Pré-flop positivo | Pendente de evidência e regra visual robusta |
| Todas as cartas em Hero e cada posição do board | Parcial; 36 cartas somente sintéticas em board_turn |
| Fold/call/raise reais | Frame e valor de call conferidos |
| Check/bet reais do Hero e todos os sizings | Pendente; rótulos sintéticos testados |
| Nomes e ações dos jogadores | Exemplos reais; não identificação por popup |
| Pot/stack/ID em todas as condições | Exemplos; cobertura geral pendente |
| Tracker e ranges reais | Esquema/exportação pendentes; contrato local testado |
| Windows, DPI e Wi-Fi físico | Não executados neste ambiente Linux |

Não há homologação de 100% do produto. Consulte `LAB_TRACKER_ENGINE.md` no
diretório pai para a fundação da política versionada e os limites da integração.
