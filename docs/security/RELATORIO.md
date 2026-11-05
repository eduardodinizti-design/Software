# Auditoria do ZIP VisualPilot — 05/11/2026

**Entrega suspensa. Não restaurar o arquivo da quarentena.**

## Amostra verificada

ZIP publicado no commit 00233c609f583c2022ff076d975c862c4b691cbb.
SHA-256: `004c4d2afc28461d9f419003297538539344045b07f6b5dc45db6c361b18984c`.
Tamanho: 36.146 bytes. São 29 arquivos: Python, CMD, PNG, JSON e TXT; nenhum EXE ou DLL embutido. Os 28 hashes do manifesto conferem. Não houve alteração para tentar evitar detecção.

## Antivírus realmente executados

- ClamAV 1.5.4, base 28171 de 01/11/2026, 3.628.245 assinaturas: ZIP e arquivos extraídos examinados, zero arquivos infectados. Container isolado sem rede durante o scan. Imagem: clamav/clamav@sha256:6d87c712e3391e13c1ba6e05dfb074d4b1ddb5a6834b23bb9da990d2a4ef042a.
- Microsoft Defender em GitHub Actions Windows: motor 1.1.26100.4, produto 4.18.26100.4, assinaturas atualizadas 1.463.144.0 de 05/11/2026. Download da amostra imutável, conferência SHA-256, extração e scan personalizado da pasta com ZIP e conteúdo. MpCmdRun retornou 0. Consultas Get-MpThreatDetection e Get-MpThreat não retornaram registros.
- Execução: https://github.com/eduardodinizti-design/Software/actions/runs/42124479170
- Evidência bruta: observer-defender-evidence.json nesta pasta.

## Limites importantes

O runner Windows informou AntivirusEnabled=true, mas RealTimeProtectionEnabled=false, BehaviorMonitorEnabled=false e IoavProtectionEnabled=false. Nenhuma proteção foi desativada pelo workflow: este era o estado inicial do runner. A verificação personalizada sob demanda foi executada; ela NÃO reproduz a análise em tempo real/reputação de download do computador do usuário. O programa não foi executado nem instalado. Dependências futuras baixadas por pip não integram esta análise.

## Inspeção do código

Inventário de imports, chamadas sensíveis, manifesto e scripts revisados. O CMD cria um ambiente Python, verifica o manifesto, instala dependências e abre o GUI local. A captura usa consulta limitada de processo e ImageGrab. Diagnósticos são gravados localmente. Não foi encontrado mecanismo explícito de transmissão de imagens, acesso remoto, captura de teclado, persistência no Windows ou roubo de credenciais no código empacotado. Isso não constitui prova absoluta de ausência de malware.

## Conclusão e próximo bloqueio

O alerta do usuário NÃO foi reproduzido pelos scans. Não é correto afirmar que há falso positivo confirmado nem certificar segurança total. Falta identificar a assinatura/família exata detectada no computador do usuário (ThreatName/ThreatID) e confrontá-la com a Microsoft. O link de entrega na branch foi retirado; a amostra permanece no histórico Git para auditoria. Uma nova entrega depende de esclarecer o bloqueio, não de renomear ou ofuscar o pacote.
