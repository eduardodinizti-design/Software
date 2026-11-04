# Lobby: captura, OCR, filtro e detalhes — 31/10/2026

Implementado no **laboratório isolado**, com PNGs do navegador e OCR real. O módulo
retorna cartões estruturados, motivos de exclusão e posições; abre um torneio por
observação e confere seus dados na tela seguinte. O limite confirmado continua
em **50 fichas fictícias por inscrição**, somando todas as parcelas do buy-in.
Não há aumento automático para 100 ou 200.

## Arquivos e fluxo

| Arquivo | Responsabilidade |
| --- | --- |
| `visualpilot/lab/lobby.py` | Segmentação calibrada, parser, filtros, histórico e controlador de uma navegação por captura |
| `visualpilot/lab/lobby_gui.py` | PNG do viewport/recorte, OCR por cartão, origem/escala das coordenadas e revalidação antes da ação |
| `visualpilot/lab/lobby_simulator.html` | Lobby e tela de detalhes fictícios, incluindo pausa/controle manual |
| `tools/check_lobby_lab.py` | Ensaio de navegador com OCR e navegação simulada |
| `tests/test_lobby.py` | Regressões numéricas, segmentação, concorrência, histórico, controle e validade |

Fluxo: PNG → cartões completos → OCR por cartão → parser → filtros e histórico →
uma seleção → revalidação de imagem/idade/controle → abertura dos detalhes → OCR
e comparação com o cartão. O retorno `registered=False` é explícito. A interface
de detalhes mostra Registrar desabilitado neste ensaio; nenhum registro é executado.

O campo de identidade do torneio é separado do nome e da posição. A comparação
nos detalhes inclui identidade, nome, tipo, buy-in, stack, horário observado e
estado de registro. Um custo diferente resulta em `unknown`, preserva o histórico
e não autoriza inscrição. Horário é texto validado `HH:MM`, sem inferir data ou fuso.

## Parser e filtros

- `28.34 + 14.16 + 7.50` e `28,34 + 14,16 + 7,50` totalizam **50,00**, usando
  `Decimal`. Nunca se utiliza somente a primeira parcela nem `float` para a soma.
- Até quatro parcelas, cada uma com no máximo duas casas decimais. Separadores
  de milhares, valores negativos, `5O`, `5 0`, `50/100` e parcelas incompletas
  ficam pendentes; não se corrigem dígitos por suposição.
- Continuação de preço pode ser reunida somente entre linhas adjacentes do mesmo
  cartão, com operadores/unidade reconhecidos e confiança válida. Nunca unir
  dados de cartões vizinhos. Espaços não são removidos de dentro de números.
- Exige moeda explicitamente fictícia, tipo, stack, horário, nome e ID legíveis.
  Confiança mínima dos campos: 0,95. Uma releitura do recorte pode confirmar o
  mesmo texto com confiança maior; divergências de dígitos não são substituídas.
- Estados distintos: `open`, `closed`, `scheduled` e `unknown`. Só **ABERTO** é
  elegível. “Ativos”, status ausente e OCR ambíguo não equivalem a registro aberto.
- IDs duplicados na mesma captura bloqueiam os candidatos correspondentes.

`LobbyRules` configura `max_buyin` (até 50), `allowed_types` (MTT/SNG no layout
suportado), `targets` opcional (até quatro IDs), `minimum_stack` e `max_candidates`
(1–4). O padrão seleciona MTT, stack mínimo de 1.000 e até quatro candidatos por
leitura, abrindo somente o primeiro elegível ainda não visitado. O limite de
candidatos não reserva vagas em torneios; o ledger de inscrições mantém essa
responsabilidade na etapa de compra já existente.

## Segmentação e coordenadas

Cartões são identificados por suas bordas completas no layout fictício, sem
pressupor altura fixa. A calibração de cor pertence ao simulador; não representa
um detector genérico de lobby PPPoker. Cartões cortados na borda da captura e
contornos quebrados não geram posições clicáveis. Há limite de 24 regiões por
captura, tamanho máximo de imagem e rejeição de geometrias inválidas.

O centro calculado inclui a origem do recorte. Somente o ponto é convertido de
pixels nativos para coordenadas do viewport. Antes de abrir, uma nova captura
deve manter hash, dimensões, origem e escala. A observação precisa continuar com
idade até cinco segundos; essa condição é verificada novamente depois da gravação
do histórico. O simulador ainda confere revisão, modo e identidade sob o ponto.

## Histórico e controle

`LobbyHistory` usa o mesmo SQLite de `RegistrationLedger`, em tabela separada.
Uma tentativa é gravada **antes** da navegação, em transação. Visitas abertas,
incertas ou canceladas ficam excluídas de novas tentativas automáticas. Torneios
já registrados e inscrições pendentes também são excluídos. Encerrar/reabrir o
processo não limpa o histórico. Não há botão de reset ou reconciliação automática
neste módulo; uma sessão nova exige escolha explícita de outro banco.

Reordenação da lista invalida a coordenada anterior. A próxima navegação exige
retornar ao lobby e obter nova captura. Não há laço que clique em todas as posições
de uma lista antiga com `sleep` entre cliques. A espera pela transação não mantém
o bloqueio de controle: assumir manual durante OCR ou gravação impede a ação seguinte.

## Evidências

O relatório e os PNGs/diários/SQLite por cenário estão em [browser/](browser/report.json).
A execução final passou nos **nove cenários em 24,088 s**, sem erros JavaScript.
Ambiente: Chromium headless no Linux, OCR real sobre o layout fictício. Os cenários exercitam:

1. Lobby misto, duas seleções em capturas separadas, conferência de custo composto
   e histórico preservado após reinício.
2. Registro encerrado, ausente e custo total de 50,01: nenhum clique.
3. Tipo não permitido, moeda real e stack insuficiente: nenhum clique.
4. ID duplicado: nenhum clique.
5. Cartão inferior parcialmente visível: somente o cartão completo é selecionado.
6. Lobby deslocado e capturado por recorte: coordenada global correta.
7. Lista reordenada depois do OCR: clique cancelado.
8. Tomada manual durante OCR: nenhum clique.
9. Custo alterado na tela de detalhes: resultado desconhecido, nenhuma inscrição.

A [regressão completa](regression.log) executou **398 testes em 137,322 s**, sem
falhas e com três casos ignorados por imagens de referência ausentes. Inclui os
14 testes novos do lobby.

Os testes unitários complementam com valores decimais exatos, custos em linhas
separadas, confiança inválida, segmentação de alturas diferentes, origem negativa,
concorrência e expiração/tomada manual durante a transação.

## Executar

Na raiz do checkout, com dependências do projeto e `requirements-lab.txt`:

```sh
PYTHONPATH=. python -m unittest discover -s tests -p test_lobby.py -v
PYTHONPATH=. python tools/check_lobby_lab.py --output diagnostics/lobby/nova-rodada
```

O ensaio exige Chromium (`--chromium` permite configurar seu caminho) e pasta de
saída vazia. O HTML também pode ser aberto para exploração manual do layout;
captura/OCR/filtro automatizados são executados pelo script.

## Limites atuais

Faltam calibração com capturas reais do lobby, paginação/rolagem, temas/idiomas
adicionais, DPI e escalas independentes, homologação Windows e ligação desta tela
de detalhes ao modal/recibo do módulo anterior. As falhas de DPI/125% da rodada
anterior não são resolvidas por este trabalho. O parser aceita centavos no lobby;
o seletor anterior ainda exige inteiros, portanto não há conversão ou truncamento
automático para inscrição.

Esta rodada não clica no PPPoker, não envia comandos entre computadores, não
registra torneios e não confirma entrada em mesas. É uma etapa verificável do
laboratório, que entrega a seleção e a comparação dos detalhes para a integração seguinte.
