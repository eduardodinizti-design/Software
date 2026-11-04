# R3 — identidade do processo no Windows

A imagem enviada mostra três falhas exclusivamente na comparação `state['pid'] == process.pid`, depois de o teste já ter confirmado resposta HTTP. Essa igualdade não é portável: o iniciador do ambiente virtual no Windows pode executar o servidor em processo filho. O número registrado pela Central não precisa ser o PID retornado por Popen.

A verificação foi substituída por token aleatório exclusivo por tentativa, build esperado, URL/porta esperada e fase ready, mantendo a exigência de HTTP 200. Não se ignora o teste e não se aceita um servidor antigo. A regressão testa rejeição de token/build/URL/fase diferentes. O encerramento usa taskkill /T /F no Windows para finalizar também processos filhos; a chamada foi testada com mock, sem afirmar execução física Windows.

Os três perfis reais (cadastro ausente, malformado, válido) passaram no Linux. Evidência em tests.log. O patch Correcao_Central_R3.zip contém 159 arquivos conferidos por SHA256 e substitui o R2. Não altera a configuração pessoal do notebook.

O identificador do programa continua central-live-20261030-r2: R3 corrige o teste/empacotamento, sem nova alteração no comportamento do servidor. A entrega Windows continua VisualPilot_Central_Corrigida.zip, contendo a pasta VisualPilot_Central_R2.

Suíte unificada após a correção: 269 testes executados, 266 aprovados, 3 ignorados, nenhuma falha (129,831 s no Linux). Não foi realizada execução física Windows neste ambiente. O instalador repetirá a suíte e a validação dos executáveis no PC principal antes de gerar o ZIP para o notebook.
