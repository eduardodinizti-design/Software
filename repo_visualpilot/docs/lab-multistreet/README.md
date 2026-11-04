# Planejamento flop–turn–river e PKO experimental

## Entrega

`visualpilot/lab/multistreet.py` compara decisões na rua atual com continuidade de apostas até
river. Atualiza pote, stack efetivo e range após cada ação. Usa a árvore anterior de uma única
rua como componente, mantendo um raise por rua e sem reraises. Heads-up, sem rake/ICM.

- Sizings configuráveis como frações do pote; padrão1/3,2/3,1 pote e all-in, limitados pelo stack.
- Rodadas encerradas por check/check ou bet/call avançam para a próxima carta; fold encerra a linha.
- Turn e river têm novas decisões condicionadas ao board e às ações anteriores.
- Posição preservada: OOP age primeiro; IP age depois. Para uma decisão IP na rua aberta, exige check adversário observado.
- Também aceita uma aposta adversária já feita (`facing_bet`), comparando fold, call e raises.
- As probabilidades de cartas respeitam os bloqueadores do range, sem conhecer a mão escondida.
- Chance amostrada para limitar custo; opção de enumerar cartas públicas com `chance_samples=0`.
- All-in antes do river usa amostragem de showdown e não cria apostas posteriores.
- Seeds independentes comparam estabilidade. Divergência deixa a decisão pendente.
- Limite de nós interrompe com `pending`, sem publicar uma escolha parcialmente calculada.

`pot` é o pote no instante da decisão. Se há `facing_bet`, inclui a aposta adversária. `stack` é
quanto o Hero ainda pode investir efetivamente; o adversário tinha esse stack efetivo antes da
aposta. Investimentos de ruas anteriores já pertencem ao pote e não são cobrados novamente.

`opponent_models.py` contém modelo sintético com resposta dependente da força categórica e tamanho
apostado. Ele é hipótese de engenharia, não estratégia do NVT, não modelo treinado, nem solver.
A estimativa por maximização em árvores amostradas pode ser otimista. Concordância entre três
seeds não elimina esse viés e não valida o modelo adversário.

## Experimentos entre ruas

Cinco situações, cada uma em três seeds. Dois cenários instáveis foram repetidos com seis cartas
amostradas por nó de chance, em vez de três: 21 buscas no total. Range inicial NVT openBTN25BB,
sem atribuir a ele qualquer estratégia pós-flop. Cenários independentes e stacks/potes controlados.

| Situação | Resultado após verificação |
| --- | --- |
| Top pair no flop | Check consistente nas três seeds sob o modelo |
| Flush draw no flop | Pendente: sizing/ação ainda variam entre seeds |
| Flush completado no turn | Check consistente sob o modelo |
| Draw não completado no turn | Pendente: sizings próximos e instáveis |
| Draw não completado no river | Bet3,33 consistente sob o modelo |

Veja `summary.json`, `experiments.log` e rastros individuais `.json.gz`. Custo observado no
laboratório: aproximadamente42s para as três buscas de top pair e141s para seis buscas de flush
draw, incluindo a rodada de refinamento. Esses tempos são custo de cálculo, não latência de OCR;
não alegamos decisão em tempo real pronta. Casos de turn/river foram muito mais rápidos.
Os experimentos originais antecederam a extensão PKO, que preserva o comportamento quando `pko=None`.

## PKO: o que está calculado

`visualpilot/lab/pko.py` exige stacks individuais, bounties, fração paga imediatamente, taxa explícita
de conversão de moeda para BB e origem dessa taxa. As quantias devem estar na mesma moeda.
A cobertura usa stacks no início do estado planejado (antes de uma aposta adversária já feita).

- Hero cobre adversário ou tem stack igual: bounty elegível se houver all-in efetivo e vitória sem empate.
- Hero não cobre: ganhar esse confronto heads-up não elimina o adversário, portanto não credita bounty.
- Fold, showdown sem eliminação e empate não recebem prêmio de eliminação.
- Parcela progressiva acrescida à cabeça do Hero é registrada separadamente; seu EV futuro é desconhecido, não dinheiro imediato.
- Utility experimental = chipEV + probabilidade de vencer sem empate × prêmio imediato convertido.
- Não calcula ICM, bounty power completo, efeitos futuros de sobrevivência, side pots ou multiway.
- O modelo adversário recebe os metadados PKO, mas o modelo sintético atual não foi calibrado para adaptar seu range a eles.

Teste analítico: equidade25%, pote15BB incluindo shove10BB. Call sem bounty temEV−3,75BB.
Com Hero cobrindo e bounty imediato equivalente20BB, call passa a+1,25BB. Sem cobertura continua
−3,75BB. O teste varia o bounty de0 a40 em dez combinações de cobertura, sem aumentar ranges por
percentual arbitrário. Registro em `pko-sensitivity.json`. A taxa usada é fictícia e explicitada.

## Leitura do exemplo enviado

`observer/bounties.py` associa nome/stack/bounty por assento num perfil geométrico candidato
para o layout PPPoker8lugares mostrado pelo usuário. Consome as linhas OCR já existentes, sem
acrescentar uma inferência pesada. Reconhecimento PKO, nome/stack/bounty têm evidências; ambiguidades
ficam pendentes. A unidade do valor exibido permanece desconhecida. Perfil não homologado.

Integração: `read_table` inclui o objeto `pko`, o arquivo de sessão o preserva e mudanças nas regiões
invalidam a leitura. **`usable_for_strategy=False`** até validar a captura original, confirmação
entre frames, unidade, regras e conversão. Não há passagem automática desses números para decisões.

Valores visualmente lidos pelo assistente na imagem do usuário, transcritos para testes de
associação de linhas OCR (não confundir com validação de OCR nos pixels originais):

| Rótulo visível | Stack BB | Bounty exibido | Hero33,8BB cobre? |
| --- | ---: | ---: | --- |
| PPODRE… |27,5|72|Sim|
| mateusbit |35,1|204|Não|
| Azulma |19,4|324|Sim|
| atzedes ed… |22,2|168|Sim|
| sacatrapoo |39,6|240|Não|
| Tainah790 |23,9|72|Sim|
| Nantes.23 |67,7|372|Não|
| Hero Just do it |33,8|72|—|

A imagem contém vários jogadores; o novo solver heads-up não resolve diretamente essa mão multiway.
O valor324 não foi tratado como324BB ou324unidades monetárias. Falta comprovar a unidade do cliente.

## Verificação do pacote NVT

O ZIP contém tabelas e cliente de consulta. As tabelas dos6349nós têm `stacks`, `actions`, `potBb`;
não têm os bounties individuais da mesa exportada. O pacote tem referências PKO/ICM, mas não o
código do motor dinâmico. A seção “B. Motor como biblioteca” em `integracao-ranges.md` distingue
explicitamente a consulta exportada do cálculo com cenário, stacks, bounties e payouts.

O leitor NVT agora rejeita uma solicitação de adaptação com `bounties`, `bounty_power` ou `pko_live`
em contexto PKO, em vez de ignorar esses dados e devolver uma tabela estática como se fosse adaptada.
Não inventamos uma versão própria da fórmula NVT sob o mesmo nome.

## Reprodução

```sh
.venv/bin/python -m tools.run_multistreet_lab
.venv/bin/python -m unittest tests.test_multistreet tests.test_pko_lab tests.test_bounty_observation -v
.venv/bin/python -m unittest discover -s tests
```

Evidências: testes analíticos de três ruas com royal flush, conservação de investimentos,
paridade com solver de river anterior, posição, caps/all-in, orçamento, PKO, empates e invalidação
visual. Não são prova de GTO, maturidade estratégica completa ou execução Windows.

Para concluir a maturidade ainda faltam: modelo adversário validado, estratégias de referência
pós-flop independentes, melhoria de precisão/custo nos draws, motor NVT de bounty power/ICM,
OCR dos bounties validado em capturas reais, multiway e integração visual de execução no simulador.

Validação final: **225 testes executados, 222 aprovados, 3 ignorados, nenhuma falha**.
Visualizador HTML: cinco situações, dois estados pendentes, alternância de cobertura PKO,
sem erros JavaScript e sem overflow em390px. Ele mostra resultados pré-calculados, não executa o solver.
