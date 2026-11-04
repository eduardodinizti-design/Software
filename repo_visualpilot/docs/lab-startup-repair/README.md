# Correção da inicialização — central-live-20261030-r2

## Falha reproduzida

O launcher anterior chamava `streamlit.web.cli.main()`. O CLI chama `check_credentials()`. Mesmo com `server.headless=true`, a existência de `credentials.toml` inválido leva à tentativa de ativação interativa. Com `sys.stdin=None`, o processo encerra com `lost sys.stdin`.

Reprodução isolada usando o launcher anterior, perfil temporário com `email = ""` sem a seção `[general]` e sem stdin: exit 255, `before.log`. Esse é precisamente o formato incompleto indicado anteriormente ao usuário. A falha inicial do notebook precedeu essa orientação; não foi comprovada a versão exata do primeiro executável nem o conteúdo anterior do perfil. Portanto, a reprodução explica um caminho confirmado para o erro persistente, não prova todas as causas da primeira tentativa.

## Correção

A Central passa a iniciar o servidor incorporado via `streamlit.web.bootstrap`, sem o fluxo opcional de cadastro de e-mail do CLI. Mantém CORS/XSRF ativos, endereço local e coleta de métricas desativada. Não cria, apaga nem corrige o perfil Streamlit do usuário. A API de bootstrap é interna do Streamlit; a versão permanece fixada em 1.50.0 e deve ser retestada ao atualizar a dependência.

Toda abertura grava `central_startup.log` e `central_status.json`, mesmo sem console. O status identifica build, PID, executável, fase e erro. Uma falha apresenta uma mensagem no Windows apontando o log, em vez de apenas desaparecer. O painel exibe a versão.

O teste de distribuição Windows agora usa dois perfis temporários: sem cadastro e com cadastro malformado, ambos com configuração conflitante. Exige identificação do build e token exclusivo, além do endpoint HTTP. O teste anterior cobria somente perfil sem cadastro e a resposta HTTP. Não era uma prova de funcionamento do pacote transferido no notebook.

## Entrega corrigida

`Correcao_Central_R3.zip` contém código de correção, manifesto SHA256, um iniciador BAT e script PowerShell. Extrair o ZIP completo no PC principal e abrir `CORRIGIR_CENTRAL.bat`. O script encontra o projeto em `C:\VisualPilot-entrega-visualpilot-piloto`, confere o patch, salva backup dos arquivos de código substituídos e executa o build existente. Configurações da distribuição são preservadas pelo build.

Somente depois de aprovada a inicialização, o build gera `dist/VisualPilot_Central_Corrigida.zip`, com a pasta inteira `VisualPilot_Central_R2`. Copiar esse ZIP para o notebook, extrair e abrir o EXE nessa nova pasta. Não misturar com a pasta antiga e não usar atalhos antigos. O pacote contém `VERSAO_CENTRAL.json` com hashes dos arquivos.

## Verificação no laboratório

`after.log`: servidor real responde em três perfis (sem cadastro, cadastro inválido, cadastro válido), sem stdin/stdout/stderr; configuração antiga headless=false é sobreposta; arquivo do usuário permanece intacto.

`browser.log`: Chromium + launcher corrigido + perfil malformado + TCP/OCR/painel, com marcação e expiração visual. `unified.log`: suíte completa.

Não há máquina Windows disponível neste laboratório. Não foram gerados EXEs Windows aqui, nem executados os scripts BAT/PowerShell no Windows. Esses passos são realizados automaticamente no PC principal. O teste físico final continua necessário; não se declara o notebook corrigido antes dele.

Resultado final: 267 testes executados, 264 aprovados e 3 ignorados. Regressão real de inicialização aprovada nos três perfis. Navegador sem erros, marcador e amostras persistidos, alerta de congelamento e tela estreita aprovados. Patch ZIP: 159 arquivos de código/recursos conferidos contra SHA256; não inclui executáveis nem substitui configurações pessoais. O PowerShell de reparo exige a pasta conhecida do projeto no PC principal e para com mensagem explícita se ela não existir.

Atualização R3: teste de identidade corrigido para iniciadores Windows com processo filho. Consulte `windows-pid/README.md`. Não utilizar novamente o pacote R2 para aplicar a correção.
