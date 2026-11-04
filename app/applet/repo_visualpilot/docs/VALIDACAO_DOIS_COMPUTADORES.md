# Teste do pacote Windows no PC e no notebook

Use o artefato **windows-laboratory-candidate** somente da execução verde de
**Windows laboratory** que contenha a correção de captura e reorganização de
mesas (build `central-live-20261030-r4-desktop-validation`). A revisão anterior
`acd1351` passou no laboratório antigo, mas apresentou problemas no teste físico.
O candidato novo exige também captura de desktop, OCR e painel dos executáveis.
Não instalar enquanto essa execução Windows não passar. Não é necessário
instalar Python ou executar o build para usar um artefato aprovado.

## Preparar os dois programas

1. Na página da execução verde, baixe `windows-laboratory-candidate` em
   **Artifacts** e extraia o ZIP inteiro.
2. Na Central antiga, clique **Parar coleta**. Depois, encerre os executáveis
   antigos `VisualPilot_Central.exe` e `VisualPilot_Coletor.exe` pelo Gerenciador
   de Tarefas. Fechar somente a aba do navegador não encerra a Central.
3. No notebook, extraia o `VisualPilot_Central_Corrigida.zip` recebido. Ele contém
   a pasta `VisualPilot_Central_Temporal_V2` e seu `VisualPilot_Central.exe`.
4. No PC de captura, coloque a pasta inteira `VisualPilot_Coletor` recebida em
   um local novo. Abra o programa dessa pasta; todos os arquivos acompanhantes
   precisam estar presentes.
5. Copie o `stream_config.ini` de cada instalação antiga para a respectiva
   instalação nova. No Coletor, confira se `host` contém o IP atual do notebook
   e preserve seu `member.id`. A porta precisa coincidir nas duas configurações
   (padrão `48735`). No Coletor novo, a janela permite preencher o endereço,
   a porta e o ID do membro e clicar **Salvar e iniciar**. O texto de exemplo
   `INFORME_O_ID_DO_MEMBRO` precisa ser substituído pelo ID usado na instalação.
   Se já utilizava `nvt_config.ini`, preserve esse arquivo na Central também;
   a coleta não depende do serviço de estratégia.

Os dois programas devem vir da mesma execução. Guarde as pastas anteriores para
referência e abra os executáveis diretamente nas pastas novas durante este teste.

## Conferir uma mesa fictícia

1. Abra `VisualPilot_Central.exe` no notebook. No painel, clique **Iniciar coleta**.
   Se o Windows solicitar permissão de firewall, permita na rede privada usada
   pelos dois computadores.
2. Deixe uma mesa fictícia visível no PC e abra o novo `VisualPilot_Coletor.exe`.
   Confira na janela os contadores de monitores, mesas e quadros enviados.
3. Confira se a prévia chega ao notebook e se as cartas legíveis do Hero e do
   board correspondem à mesa. Na mudança de mão, confira se as cartas anteriores
   deixam de aparecer como atuais.
4. Encerre o Coletor no PC e aguarde mais de cinco segundos. A Central deve
   sinalizar falta de atualização e deixar de apresentar as cartas antigas como
   leitura atual. Abra o Coletor novamente e confira se chega uma leitura nova.
5. Clique **Parar coleta** na Central e guarde a pasta da sessão indicada no
   painel. Ela contém os registros necessários para analisar atraso, descarte
   ou divergência.

Depois repita com três mesas visíveis, mova e reorganize as janelas no PC.
Confirme que todas retomam a atualização e que não sobram registros duplicados
congelados. Sem Hero sentado, a imagem deve continuar chegando e as cartas do
Hero devem permanecer pendentes. Guarde também `collector.log` e
`collector_status.json`; erros de processamento ficam em `erros_ocr.jsonl`
na sessão da Central.

O retorno inicial necessário é: a prévia apareceu, as cartas coincidiram e o
encerramento/reabertura do Coletor atualizou corretamente o estado. Se houver
erro, informe a mensagem e em qual passo ocorreu. Esse teste verifica a instalação
física; a execução verde do GitHub não substitui esse resultado.
