# Auditoria da sessão enviada em 2026-10-30

ZIP recebido: 14 entradas, 6.655.189 bytes compactados. Sessão iniciada às 17:32:35 (America/Sao_Paulo); diário de percepção de 17:40:44 a 17:55:12. A diferença até o primeiro registro não é tratada como tempo de inicialização: houve configuração de rede durante o ensaio.

## Evidências

- 171 registros no diário: 169 parciais e 2 pendentes. Nenhum publicou cartas do Hero ou board.
- Métricas: 91 erros, 837 resultados de regiões de cartas, 3 publicações consolidadas, 1 expirada e 0 resultados reaproveitados do cache. O diário deduplica consolidações idênticas; 3 publicações não obrigam 3 linhas distintas.
- Duas identidades de mesa. Isso não comprova duas mesas físicas simultâneas durante todo o teste.
- Cinco arquivos PNG, representando três amostras distintas; um marcador manual às 17:45:45.
- As parciais registram 676 regiões pendentes com mensagem de cartas incompletas/ambíguas. Não são leituras bem-sucedidas apenas por terem baixa latência.
- Uma leitura bruta reconheceu pote, stack, ID e badges, mas foi invalidada por idade de 12,203 s. Outra registra timeout. As métricas não identificam individualmente a causa de todos os 91 erros; não se afirma que todos foram timeouts.

## Conferência visual e replay

Na primeira imagem são visíveis flop 2c/4h/9c e cartas Th/6c escurecidas após fold. As cartas têm fundos verdes/vermelhos e glifos claros. O detector atual usa componentes claros/neutros para localizar as cartas; no replay continuou retornando Hero/board vazios. O problema do board é real, pois ele está visível na evidência.

As outras duas amostras mostram intervalo de add-on, sem cartas visíveis. Lista vazia nesses frames não constitui erro de reconhecimento de cartas, mas o painel deveria distinguir pausa de torneio de falha de leitura. Não há prova de detecção/execução de compra de add-on: a imagem mostra uma contagem de intervalo, não um recibo nem uma compra.

Replay local com OCR atual, sem alterar os leitores: primeira imagem em 1,854 s, pote 3,4 BB e stack 35,5 BB lidos, sem cartas; demais imagens em 1,090 e 1,393 s, stack 33,3 BB lido, sem cartas. Esses tempos não homologam desempenho no notebook nem reproduzem a causa dos timeouts Windows. `replay.json` guarda resultados e caixas; imagens e histórico original do usuário permanecem no workspace, sem nova publicação no repositório.

## Conclusão

Transmissão e gravação demonstradas; leitura de cartas não aprovada. A cobertura anterior de cartas brancas não se transfere ao tema colorido desta sessão. Próximos reparos: suporte testado a esse tema, validação dos recortes/calibração, observabilidade dos erros por trabalho e latência de inferência real, e estado explícito de intervalo/add-on. Não solicitar nova sessão longa antes de reproduzir e corrigir as falhas com as evidências existentes.
