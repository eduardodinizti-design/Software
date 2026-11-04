# Inscrição integrada com localização visual — 31/10/2026

O fluxo de laboratório agora executa **localizar → ler → ajustar → reler →
registrar uma vez → conferir recibo** usando posições encontradas no PNG.
Limites preservados: 50 fichas fictícias por inscrição, até quatro torneios
simultâneos, orçamento de inscrições e reservas persistentes. Custo e stack
continuam separados.

Resultado: **16 verificações atendidas e duas configurações ainda não aprovadas**
entre 18 cenários de navegador. O relatório usa `passed_with_limits`, não aprovação
geral. DPI alto e escala de 125% foram bloqueados sem cliques; não baixar limiares
nem tratar esses bloqueios como sucesso de inscrição.

## Mudanças

| Arquivo | Função |
| --- | --- |
| `visualpilot/lab/button_locator.py` | Carrega templates, procura correspondências, elimina picos sobrepostos e rejeita múltiplos candidatos distintos |
| `visualpilot/lab/assets/registration/` | Templates do simulador para Mais/Menos/Registrar e manifesto com hashes; não são imagens do PPPoker |
| `visualpilot/lab/registration_gui.py` | Captura viewport/recorte PNG em pixels nativos, localiza botões, faz OCR e converte coordenadas para o navegador |
| `visualpilot/lab/registration_simulator.html` | Recebe coordenada e confere o elemento atingido, modo e revisão antes da ação simulada |
| `visualpilot/lab/registration.py` | Mantém limites, ajuste verificado e recibo; propaga a causa específica de recusa do adaptador |
| `tools/check_registration_lab.py` | Integra captura, detecção, OCR, coordenadas e inscrição nos 18 cenários |
| `tests/test_button_locator.py` | Testa origem do recorte, origem negativa, escala, ambiguidades e entradas inválidas |

O detector usa `TM_CCOEFF_NORMED`, limiar 0,92 e escalas explícitas. Não escolhe
simplesmente o primeiro pixel acima do limiar: picos próximos são agrupados, mas
dois botões distintos permanecem ambíguos. Template ausente, sem detalhes,
corrompido ou maior que a área disponível não autoriza clique. Há limites de
imagem, escalas e candidatos. Correlação de template não é probabilidade de acerto.

Mais e Menos são localizados separadamente. Não há offsets fixos como “100 pixels
à esquerda de Registrar”. As coordenadas incluem a origem do recorte; depois são
convertidas da resolução nativa para o viewport. Não se reduz o PNG para fazer
essa conversão. A revisão da captura inclui um contador próprio: coordenadas
consumidas não podem ser reaproveitadas, mesmo se a revisão do popup não mudou.

Antes de cada ação, o adaptador captura novamente a mesma área e confere pixels,
geometria e idade. Se houve mudança, devolve uma recusa explícita. O simulador
ainda confere a revisão e o botão sob a coordenada no momento da execução. A
escolha da posição vem da imagem; o DOM serve apenas como barreira do simulador.
Esse mecanismo não comprova a mesma atomicidade em um programa externo.

Não se clica em Registrar para descobrir o custo: no layout simulado, o popup já
exibe os dados e esse botão confirma a compra. O único clique final ocorre após
ler o valor alvo e reservar orçamento/vaga. Uma interface com botão de entrada e
confirmação separados exigirá estados e evidências próprios.

## Regressão final

**384 testes em 135,959 s, sem falhas**, com três casos ignorados por imagens de
referência ausentes. [Log completo](regression.log). Inclui os seis testes novos
de localização e os 15 testes de inscrição existentes. Aprovação dessa suíte
não elimina as duas falhas de configuração visual registradas abaixo.

## Evidências de navegador

[Relatório final](browser/report.json), imagens e diários por cenário em `browser/`.
Cada `observations.jsonl` guarda texto/confiança OCR, imagem, hash, origem,
dimensões e candidatos. `clicks.jsonl` registra coordenada na imagem, coordenada
no viewport, aplicação ou recusa e sua causa. Os SQLite guardam as reservas.

| Cenário | Resultado observado |
| --- | --- |
| Incremento 10→50 / decremento 60→50 | Inscrições confirmadas pelo recibo |
| Popup deslocado | Ajuste e registro confirmados nas novas coordenadas |
| Captura recortada com origem diferente de zero | Decremento e registro confirmados |
| Seletor sem progresso | Um ajuste, bloqueio e nenhuma inscrição |
| Custo malformado | Nenhum clique |
| Tomada manual durante OCR | Nenhum clique |
| Popup trocado ou movido após observação | Nenhum clique; `image_changed_before_click` |
| Dois botões Registrar / botão ausente | Nenhum clique |
| Texto Registrar sem botão | Nenhum clique; correspondência visual insuficiente |
| Reutilizar a mesma coordenada | Segunda tentativa recusada; nenhum clique duplicado |
| Recusa explícita | Inscrição rejeitada, contabilizada como tal |
| Popup fechado sem recibo | Resultado desconhecido, reserva mantida |
| Quatro inscrições e tentativa de quinta | Quinta bloqueada pelo limite simultâneo |
| DPR 2 e popup ampliado a 125% | Não aprovados; zero cliques nas duas tentativas |

Ensaio final: 58,359 s, Chromium headless no Linux, OCR real sobre PNGs do próprio
simulador; nenhum erro JavaScript. Não houve captura de desktop do usuário ou
tráfego de comandos para outro computador.

### Falhas de DPI/escala preservadas

A primeira rodada tentou reduzir o PNG de DPR 2 à resolução CSS. O OCR leu
`Pass0: 5` e os templates não atingiram o limiar. Evidências em
[before-native-pixels.json](before-native-pixels.json) e `before-native-pixels/`.
A versão atual mantém os pixels nativos e converte somente o ponto.

Isso corrige a representação das coordenadas, mas não certifica o reconhecimento:
no ensaio nativo, templates interpolados tiveram correlações próximas de 0,89,
abaixo de 0,92. A sondagem em `native-dpi-probe/` também contém `1o` no lugar de
`10` e baixa confiança no passo. Esses dígitos não foram corrigidos por suposição.
No ensaio final, DPR 2 bloqueou por campo pouco legível; 125% bloqueou por campo
ausente/ambíguo. Precisam de templates e cobertura OCR independentes antes de uso.

## Reprodução

Na raiz do checkout, com dependências do projeto e de `requirements-lab.txt`:

```sh
PYTHONPATH=. python -m unittest discover -s tests -p test_button_locator.py -v
PYTHONPATH=. python -m unittest discover -s tests -p test_registration.py -v
PYTHONPATH=. python tools/check_registration_lab.py --output diagnostics/registration-locator/nova-rodada
```

O ensaio exige pasta de saída vazia e Chromium (`--chromium` configura o caminho).
É necessário inspecionar `status` e `known_gaps`: término sem exceção com
`passed_with_limits` não certifica todas as configurações. Os testes de localização
com imagens sintéticas verificam matemática e recusas; não substituem o ensaio
de texto e botões renderizados no navegador.

## Escopo restante

Ainda pendentes: DPR/escala acima, outros estilos de popup, abertura de inscrição
a partir de um lobby, validação Windows e integração de comandos entre Coletor e
Central. O sistema real continua observacional; as ações desta rodada alteram
somente o simulador isolado. Fechamento de popup não foi promovido a confirmação.
