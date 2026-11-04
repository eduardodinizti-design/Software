# Auxiliares integrados ao controlador

Implementação em `visualpilot/lab/lobby.py`, usada por `open_next_tournament`
e pela revalidação de detalhes de `RegistrationController`. O adaptador visual
continua responsável por captura, OCR e ação isolada na página de laboratório.

| Auxiliar | Contrato |
|---|---|
| `obter_torneios_validos(adapter, history, rules)` | Nova captura e OCR pelo adaptador; retorna `(captura, avaliação)`, com `avaliação['eligible']`, motivos de rejeição e log. Exclui o histórico antes de limitar candidatos. |
| `validar_detalhes(seleção, captura)` | Retorna os campos verificados ou lança erro com motivo; exige igualdade completa de ID, nome, tipo, custo, stack, horário e estado. Confere origem de laboratório e validade de cinco segundos. |
| `clicar_posicao(adapter, seleção, captura, control, revisão)` | Exige cartão pertencente à captura, posição e limites correspondentes; revalida controle e idade antes de delegar ao adaptador. Não aceita somente `(x, y)`. |

O adaptador `LobbyGUI.open_card` ainda verifica os pixels atuais, geometria,
revisão da página, correspondência do alvo e consumo único da coordenada.
Essas verificações não foram substituídas por uma chamada direta ao PyAutoGUI.
O fluxo principal continua reservando a visita antes de clicar e registra falhas.

Não use o auxiliar de clique em um laço sobre posições antigas. Após abrir um
torneio, outro ciclo precisa de nova captura do lobby. O método de obtenção apenas
observa; o controlador é responsável por autorizar o ciclo com o controle atual.

Novos testes cobrem captura associada à seleção, log de leitura, comparação por
nome completo/ID, imagem vencida ou externa, coordenada adulterada e pausa antes
do clique. As duas suítes afetadas passaram: **28 testes de lobby e 30 de inscrição**.
Não foi repetida a suíte global nesta refatoração; seu resultado de 422 testes
pertence ao commit anterior, conforme o relatório principal.

Esta adaptação continua no laboratório. Capturas reais e cliques no PPPoker
dependem da calibração e homologação já documentadas; as imagens inline não foram
tratadas como se fossem arquivos PNG disponíveis para testar OCR.

A [nova rodada visual](helpers-validation.json) passou nos dez cenários com OCR
real em 46,767 s, sem erros JavaScript. Os PNGs e diários desta execução estão
em `diagnostics/lobby-helpers/browser/` no workspace; o relatório foi versionado.
