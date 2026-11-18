# Achados — DADOS da MÃO do PPPoker (fase 2 do tracker, via IL2CPP/Protobuf)

Recon READ-ONLY (recon_hands.js) em 17/11/2026, PPPoker v228, IL2CPP v31. Frida
anexa OK em PPPoker.exe. Objetivo: ler a mão COMPLETA (jogadores, cartas, ações,
pote, showdown) dos DADOS do jogo — nosso próprio Hand2Note, sem OCR nem o conversor
externo pesado.

## A descoberta-chave: o jogo usa PROTOBUF
Toda a comunicação de jogo está em **`PP.Production.Protocol.dll`**, namespace **`Pb`**
(classes Protobuf). O estado da mão chega por mensagens `*BRC` (broadcast servidor→
cliente), `*REQ`/`*RSP` (request/response). Decodificar essas mensagens = mão completa.

## Mensagens genéricas de HOLDEM/NLH já localizadas
- `Pb.SeatStatus` — estado do assento (provável: id jogador, stack, aposta, status, cartas).
- `Pb.PlayerHoleCard`, `Pb.HandCardRSP`, `Pb.ViewHandCardRSP` — cartas do herói.
- `Pb.ShowAllHoleCardREQ/RSP` — cartas mostradas no showdown.
- `Pb.MultipleTableHoleCardItem` / `Pb.MultipleTableHoleCardRSP` — cartas por mesa (multi-tabling).
- `Pb.MttPlayerInfo` — info do jogador em MTT.
- `Pb.DealerInfoRSP`, `Pb.PotFoldType`, `Pb.BombPotStartBRC`.
- Avaliação de mão (utilitários, não estado): `PP.Basic.HoldemOdds.{PokerCard,HandType,BestHand,PokerHands,CardUtils}`.

## CONJUNTO DE MENSAGENS da mão (recon_pb.js, 2494 classes Pb dumpadas em recon_pb_out.txt)
Mensagens-alvo p/ reconstruir uma mão NLH (hookar o dispatch/deserialize READ-ONLY):
- `Pb.EnterRoomRSP` — estado COMPLETO da mesa ao entrar (assentos, jogadores, blinds).
- `Pb.RoomInfoUpdateBRC` + `Pb.RoomInfo` — updates incrementais da mesa (provável: carrega
  SeatStatus a cada ação + cartas públicas/board). É o candidato nº1 p/ o fluxo da mão.
- `Pb.SeatStatus` — estado por assento (id, stack, aposta, status, ação).
- `Pb.HandCardRSP` / `Pb.PlayerHoleCard` / `Pb.ShowMyCardBRC` — cartas do herói.
- `Pb.ShowAllHoleCardRSP` — cartas reveladas no showdown.
- `Pb.WinnerRSP` — resultado/ganhador/pote.
- `Pb.MttSynDealBRC` — deal/início de mão em MTT.
Falta confirmar ao vivo: onde o BOARD (flop/turn/river) chega (provável dentro de
RoomInfoUpdateBRC) e os campos exatos (só o dump ao vivo revela).

## O DISPATCHER (ponto de HOOK) — ACHADO
`PP.PPPoker.ProtocolPacketHandler`1` (GENÉRICO, um por tipo de mensagem) + interface
`PP.PPPoker.IProtocolPacketHandler`, em `PP.Production.PPPoker.dll`. Cada mensagem Pb.T
tem um `ProtocolPacketHandler<T>` com um método de tratamento (Handle/OnReceive). Hook
read-only nesse método p/ cada T-alvo = recebemos o objeto da mensagem e lemos os campos.

## *** PROVADO AO VIVO (17/11): hook lê a mão pelos dados ***
`PP.PPPoker.AppProtocol` tem os handlers da mão: OnRoundStartBRC, OnHandCardRSP,
OnActionBRC, OnActionNotifyBRC, OnRoundOverBRC, OnWinnerRSP, OnShowHandRSP, OnEnterRoomRSP,
OnSitDownBRC, OnStandUpBRC, OnSeatStatusBRC. Cada handler tem endereço PRÓPRIO (não
compartilham) — hookar cada um (hook_app.js). O **1º arg (args[1]) É o objeto-mensagem
Protobuf**; args[2] = contexto. hook_fields.js dumpa os campos (il2cpp_class_get_fields +
field_get_offset). Resolve método: il2cpp_class_from_name + class_get_method_from_name;
addr = MethodInfo.readPointer() (1º campo). Interceptor.attach(addr). TUDO READ-ONLY.

ESTRUTURA DECODIFICADA — `Pb.ActionBRC` (uma AÇÃO):
  seatid_@28 (int)       = assento que agiu
  actionType_@32 (int)   = tipo da ação (enum: fold/check/call/bet/raise/allin — mapear valores)
  chips_@40 (int)        = fichas desta ação
  handChips_@48 (int)    = total comprometido na mão pelo assento
  (campos *FieldNumber/*DefaultValue/_parser @ offsets baixos = metadata estática do protobuf-gen, ignorar)

## MAPA DE CAMPOS COMPLETO (decodificado ao vivo, hook_fields2.js)
- `RoundStartBRC`: stage_@28, board_@32 (RepeatedField = cartas comunitárias), curBlind_@40,
  riverSqueeze_@48, secondBoard_@56, **handCard_@64 → HandCardRSP** (mão do herói no início).
- `HandCardRSP`: **card1_@28, card2_@32** (as 2 cartas do herói), card3..6 (variantes), canViewHand_@56, isAllin_@57.
- `ActionBRC`: seatid_@28, actionType_@32 (ENUM), chips_@40, handChips_@48.
- `ActionNotifyBRC`: seatid_@28 (de quem é a vez), callNeedChips_@32, minChipin_@40, maxChipin_@48, canActionNum_@56.
- `AnteBRC`: info_@32 (RepeatedField), ante_@40.
- `RoundOverBRC`: pool_@24 (RepeatedField = potes). `WinnerRSP`: ganhadores/pote (dumpar completo).
- `EnterRoomRSP`: assentos/jogadores/stacks (dumpar — tem os player IDs numéricos p/ o HH).

### ENCODING das CARTAS (confirmado): `card = naipe*256 + rank`
  naipe = card >> 8 (1..4) ; rank = card & 0xFF (2..14, onde 11=J 12=Q 13=K 14=A).
  Ex.: 779=3*256+11=J(naipe3), 1038=4*256+14=A(naipe4). Mapear naipe 1..4 -> c/d/h/s (confirmar).

## PERCEPÇÃO de MESA FINAL / ICM (capturado ao vivo 17/11) — `MttProtocol.OnMttMyRankInfoBRC`
`Pb.MttMyRankInfoBRC` (broadcast periódico, 1 por mesa; dispara em mudança de rank):
  rank_@28                      = minha posição atual (0 = ainda não ranqueado/atualizando)
  itmPlayerNum_@32              = lugares pagos (In The Money)
  totalPlayerNum_@36            = total de entradas do torneio
  currentRewardPpcoins_@40      = meu prêmio garantido AGORA (PPcoins)
  currentRewardTicketPrice_@48  = prêmio em ticket
  currentRewardItemPrice_@56    = prêmio em item
  alivePlayerNum_@64            = JOGADORES VIVOS restantes  *** sinal-chave de FT/bolha ***
  satelliteRemainingTicketNum_@72 = tickets de satélite restantes
  targetStackAchievedPlayerNum_@80 = quantos atingiram o target stack (satélite)
Ex. vivo: rank=3 itm=9 total=58 alive=8 reward=14640 → FT de 9, restam 8, no dinheiro.
Fase derivável de (alive, itm, ft_size): bolha=alive próximo de itm+; ITM=alive<=itm;
FINAL TABLE=alive<=ft_size(8/9); HU=alive==2. Módulo: _repo_software/mtt_rank.py.
Hook read-only: hook_mtt.js (MttProtocol OnMttMyRankInfoBRC/OnMttDivideRewardBRC/...).

## CICLO DE VIDA da MÃO + ENUM (decodificado ao vivo 18/11, hook_sequence.js)
Sequência por mão:
  AnteBRC + rajada ActionBRC(actionType=10) → antes postadas
  RoundOverBRC (separador)
  RoundStartBRC stage=1 curBlind=SB → PREFLOP
  HandCardRSP card1 card2 → cartas do herói dadas
  ActionBRC actionType=8 (post SB, chips=curBlind) / =9 (post BB, chips=2*curBlind)
  ActionBRC/ActionNotifyBRC → ações do preflop (Notify diz de quem é a vez + ações legais)
  RoundOverBRC → fim da aposta da rua
  RoundStartBRC stage=2/3/4 → FLOP/TURN/RIVER (board em RoundStartBRC.board_ RepeatedField)
  WinnerRSP (1+ por pote/ganhador) → mão encerra
enum actionType: 1=fold 2=check 3=call 7=bet/raise(contexto) 8=postSB 9=postBB 10=postAnte.
  (PENDENTE: códigos distintos de RAISE e ALL-IN — candidatos 4/5/6, não vistos; por ora
   7=agressão, all-in inferido por chips/isAllin.)
stage: 1=preflop 2=flop 3=turn 4=river. curBlind=SB, BB=2*curBlind, ante do AnteBRC.
Cartas confirmadas: HandCardRSP 1028,1036=Q4(suit4); 771,782=A3(suit3) → decoder OK (naipe ainda a mapear).
MÓDULOS (em _repo_software, 33 testes OK): ppp_cards.py (decode_card), ppp_actions.py
(to_hh_action/stage_name), hand_history_emit.py (emit_hand, round-trip c/ hand_history),
mtt_rank.py (fase/FT). FALTA p/ fechar: ler board_ e WinnerRSP (RepeatedField), separar
MESAS no multi-tabling (sem id na msg — achar discriminador: args[0]=this handler, ou
campo room/table), mapa assento→conta (EnterRoomRSP, não disparou=herói já sentado), e o
ACUMULADOR (stream→dict→emit→hand_sink dia/torneio).

## BOARD + DISCRIMINADOR DE MESA + DEAL (recon 18/11)
- BOARD RESOLVIDO: RoundStartBRC.board_ = RepeatedField`1 com `array@16` (ptr p/ int32[]) e
  `count@24`. Elementos do array IL2CPP em +0x20 (4 bytes cada). Confirmado ao vivo:
  count=3 vals=[1029,260,776] = 5(naipe4) 4(naipe1) 8(naipe3). (turn=4 cartas, river=5.)
- DISCRIMINADOR DE MESA: NÃO resolvido. AppProtocol é SINGLETON (args[0]=0x...88e0 e seu
  campo Tag@0 são CONSTANTES em todas as mesas). ActionBRC/RoundStartBRC NÃO têm roomId.
  args[2] = inteiro pequeno (0xdc7606, não-objeto) — provável tamanho/handle, não id de sala.
  => multi-tabling fica como OPEN (candidatos p/ investigar: roomId no EnterRoomRSP + um
  "current room" em algum RoomManager estático, ou correlação por janela/HWND). SINGLE-TABLE
  (um torneio/FT por vez) já funciona sem discriminador.
- DEAL = EvChop (EV chop), em TableProtocol, NÃO MttDivideReward. Handlers: OnEvChopInfoBRC
  (proposta), OnEvChopOperationBRC/RSP (voto), OnEvChopOverBRC (fim/cancelado). hook_deal.js
  e alerta_ft.js agora escutam EvChop (+ MttDivideReward por garantia). FALTA capturar a
  estrutura do EvChopInfoBRC num deal real (campos da divisão) + coords dos botões aceitar/rejeitar.

## FALTA (mecânico, mesmo padrão):
Dumpar os campos de RoundStartBRC (blinds/btn/deal), HandCardRSP (cartas herói), WinnerRSP
(ganhador/pote), EnterRoomRSP (assentos/jogadores/stacks), e mapear o enum actionType.
Depois: acumulador mensagens->mão->formato TEXTO Hand2Note. Cartas provavelmente são
arrays/bytes (ler PbArray). Strings de id: PP player id (int) -> usar como no HH (IDs numéricos).

## MAPA COMPLETO da fase 2 (discovery FEITO; falta a IMPLEMENTAÇÃO)
1. [feito] Frida anexa; Protobuf em PP.Production.Protocol.dll (ns Pb).
2. [feito] Mensagens da mão: EnterRoomRSP, RoomInfoUpdateBRC/RoomInfo, SeatStatus,
   HandCardRSP/PlayerHoleCard/ShowMyCardBRC, ShowAllHoleCardRSP, WinnerRSP, MttSynDealBRC.
3. [feito] Dispatcher: ProtocolPacketHandler`1.Handle(T).
4. [TODO] Hookar (read-only) o Handle dos T-alvo; achar o método exato (class_get_methods
   de ProtocolPacketHandler`1) e resolver o Handle por tipo (via a instância registrada por T).
5. [TODO] Ler os campos do objeto Pb (il2cpp_field_* ou offsets do dump) numa mão real → mapear.
6. [TODO] Acumular eventos → mão fechada; emitir no formato TEXTO do Hand2Note (ou JSONL);
   salvar <base>\ANO\MÊS\DIA\<torneio>.txt. Reusar nosso hand_history.py (já parseia o formato)
   p/ validar o que emitimos.

## Plano (multi-passo, iterativo)
1. Recon dirigido p/ achar o BRC de fluxo da mão + o deal de board + o settle.
2. Hookar o HANDLER/deserialize dessas mensagens (read-only) e DUMPAR uma mensagem real
   (campos) de uma mão ao vivo → mapear os campos.
3. Montar um acumulador: mensagens → eventos da mão (begin/action/board/showdown/result).
4. Emitir no FORMATO TEXTO do Hand2Note (ver C:\Hand2Note4Hh\PPPoker\...\*.txt: PokerStars-
   style, IDs numéricos, "Dealt to", "*** FLOP ***", "*** SUMMARY ***") OU no nosso JSONL.
5. Salvar no padrão pasta/dia + arquivo/torneio.

## Risco (ciente)
Attach do Frida JÁ instrumenta o processo (parte "invasiva"); é READ-ONLY (não chama
método, não altera estado). Ver [[nvt-hotkeys-politica]]: injeção só p/ ler/organizar,
nunca ação na conta. O conversor externo que o usuário já usava faz algo equivalente.
