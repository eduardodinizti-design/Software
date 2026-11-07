/**
 * Glossário para quem está começando: o que cada número da tela quer dizer, em linguagem simples, e uma frase com
 * o número do spot ("+15% contra o BB quer dizer…"). Usado nas notas com asterisco e nos balões dos termos.
 * Regra: uma frase curta (short) para o balão e uma explicação de 2–3 frases com exemplo (long).
 */
export type TermId =
  | "risk_premium" | "bubble_factor" | "icm" | "chip_ev" | "bounty_power" | "equity_drop" | "cover"
  | "equity" | "pot_odds" | "ev" | "nash" | "fold_equity" | "resteal" | "mix"
  | "vpip" | "pfr" | "steal" | "three_bet" | "fold_to_3bet" | "cbet" | "fold_to_cbet" | "check_raise" | "wtsd" | "wsd";

export interface GlossaryEntry { term: string; short: string; long: string }

export const GLOSSARY: Record<TermId, GlossaryEntry> = {
  risk_premium: {
    term: "Risk premium",
    short: "Equity extra que o ICM exige, além da conta normal, para entrar num all-in.",
    long: "Perto do dinheiro, perder fichas dói mais do que ganhar ajuda: cair do torneio custa o prêmio que você já estava perto de garantir. Por isso um all-in que daria lucro em fichas pode dar prejuízo em dinheiro. O risk premium diz quantos pontos de equity a mais você precisa. Ex.: +15% contra o BB = se a conta das fichas pede 40%, com o ICM você precisa de uns 55%.",
  },
  bubble_factor: {
    term: "Bubble factor",
    short: "Quantas vezes perder um all-in custa mais do que ganhá-lo acrescenta.",
    long: "É a mesma ideia do risk premium, em outra escala. Bubble factor 1 = fichas valem igual nos dois sentidos (cash game). Bubble factor 1,6 = perder o all-in tira 1,6× o que ganhá-lo daria, em valor de prêmio. Quanto maior, mais apertado você joga contra aquele adversário.",
  },
  icm: {
    term: "ICM",
    short: "Conta que transforma fichas em dinheiro (valor de prêmio) no torneio.",
    long: "O ICM (Independent Chip Model) estima quanto do prize pool cada stack vale. Dobrar as fichas não dobra o valor: quem tem muito ganha pouco a mais, e quem cai perde tudo. Por isso, nas fases com premiação perto (pré-ITM, bolha, mesa final), as decisões ficam mais apertadas que no chip EV.",
  },
  chip_ev: {
    term: "Chip EV",
    short: "Conta só em fichas: cada ficha vale o mesmo.",
    long: "Chip EV é decidir pelo que dá mais fichas em média, como num cash game. Vale no começo do torneio, longe da premiação. Perto do dinheiro, o ICM muda a conta.",
  },
  bounty_power: {
    term: "Bounty power (BP)",
    short: "Quanto vale a cabeça de um jogador em relação ao stack dele.",
    long: "BP = bounties iniciais na cabeça ÷ stacks iniciais no stack. Quem tem cabeça grande e stack pequeno tem BP alto: eliminar ele rende muito, então vale pagar o all-in dele com mãos piores. BP perto de 1 = cabeça do tamanho normal para o stack.",
  },
  equity_drop: {
    term: "Equity drop",
    short: "Quanto de equity a menos você precisa para pagar quem você cobre, por causa do bounty.",
    long: "Se você ganhar o all-in contra quem você cobre, leva também o bounty dele. Esse prêmio extra baixa a equity que você precisa para o call valer a pena. Ex.: equity drop de 5% = se a conta pedia 40%, com o bounty bastam uns 35%. Contra quem te cobre não há desconto para você.",
  },
  cover: {
    term: "Cover / Covered",
    short: "Quem tem mais fichas \"cobre\" o outro: pode eliminá-lo num all-in.",
    long: "▲ COVER = você tem mais fichas que ele: se ganhar, ele sai do torneio (e no PKO você leva o bounty). ▼ COVERED = ele tem mais fichas: se você perder, quem sai é você.",
  },
  equity: {
    term: "Equity",
    short: "Chance de a sua mão ganhar o pote se as cartas forem até o fim.",
    long: "Equity de 40% = em 100 vezes que esse all-in acontecer, você ganha umas 40. Contra um range (várias mãos possíveis do adversário), é a média contra todas elas.",
  },
  pot_odds: {
    term: "Pot odds",
    short: "Equity mínima para o call se pagar: quanto você paga ÷ pote final.",
    long: "Se você paga 5 para um pote que fica com 15, precisa ganhar pelo menos 5 em 15 = 33% das vezes. Acima disso o call dá lucro; abaixo, é melhor foldar. ICM e bounty mudam esse número para cima ou para baixo.",
  },
  ev: {
    term: "EV",
    short: "Lucro médio de uma ação, comparado com foldar.",
    long: "EV (valor esperado) é quanto a jogada rende em média se você repetir a situação muitas vezes. +0,30bb = ganha em média 0,3 big blind a mais que o fold. Em ICM aparece em % do prize pool.",
  },
  nash: {
    term: "Nash (equilíbrio)",
    short: "Estratégia que ninguém consegue explorar: a resposta \"de livro\".",
    long: "No equilíbrio de Nash, cada jogador joga o melhor contra o outro, e ninguém ganha mudando sozinho. É a referência quando você não sabe nada do adversário. Contra quem erra muito, a jogada mais lucrativa é a de exploit (ajustada ao perfil).",
  },
  fold_equity: {
    term: "Fold equity",
    short: "O que você ganha quando o adversário desiste.",
    long: "Num shove, você ganha de dois jeitos: o adversário folda e você leva o pote na hora, ou ele paga e você ganha na mesa. Quanto mais ele folda, mais mãos fracas viram shove lucrativo.",
  },
  resteal: {
    term: "Resteal",
    short: "All-in por cima de um open, roubando o roubo.",
    long: "Alguém abre (muitas vezes só para roubar os blinds) e você vai all-in por cima. Funciona porque o open costuma ser largo e não aguenta pagar o all-in com a maioria das mãos.",
  },
  mix: {
    term: "Mix",
    short: "A mão é jogada de mais de um jeito no equilíbrio, e as duas respostas são aceitas.",
    long: "Algumas mãos estão no limite: o solver às vezes paga, às vezes folda, porque o lucro das duas é quase igual. No trainer, qualquer ação com frequência relevante (5% ou mais) conta como certa.",
  },
  vpip: { term: "VPIP", short: "% das mãos em que o jogador coloca dinheiro voluntariamente.", long: "Mostra quantas mãos ele joga. Baixo (15%) = tight, escolhe bem as mãos. Alto (40%+) = joga muita coisa, range fraco." },
  pfr: { term: "PFR", short: "% das mãos em que ele aumenta antes do flop.", long: "Perto do VPIP = agressivo (quando entra, aumenta). Muito abaixo do VPIP = paga muito e aumenta pouco (passivo)." },
  steal: { term: "Steal", short: "% das vezes que ele abre do CO, BTN ou SB quando todos foldaram.", long: "Steal alto = abre largo para roubar os blinds. Contra ele, os resteals e as defesas ficam mais lucrativos." },
  three_bet: { term: "3-Bet", short: "% das vezes que ele reaumenta um open.", long: "3-Bet baixo (3–5%) = só reaumenta com mãos muito fortes. Alto (12%+) = reaumenta com muita mão fraca também; dá para pagar e voltar mais." },
  fold_to_3bet: { term: "Fold para 3-Bet", short: "% das vezes que ele desiste quando reaumentam o open dele.", long: "Alto (65%+) = abre e larga: 3bet e resteal funcionam bem contra ele. Baixo (40%) = paga muito: reaumente com mãos mais fortes." },
  cbet: { term: "C-Bet", short: "% das vezes que quem aumentou antes do flop aposta no flop.", long: "C-Bet muito alto = aposta quase sempre, inclusive sem nada: dá para defender mais contra ele." },
  fold_to_cbet: { term: "Fold para C-Bet", short: "% das vezes que ele desiste da aposta de continuação no flop.", long: "Alto = larga fácil no flop: suas c-bets rendem mais contra ele." },
  check_raise: { term: "Check-Raise", short: "% das vezes que ele passa e depois aumenta no flop.", long: "Alto = agressivo no flop, devolve muita aposta com check-raise." },
  wtsd: { term: "WTSD", short: "% das mãos que ele leva até o showdown depois de ver o flop.", long: "Alto = paga até o fim com frequência (call station): blefe menos contra ele." },
  wsd: { term: "W$SD", short: "% dos showdowns que ele ganha.", long: "Alto = quando chega ao showdown tem mão. Baixo = vai ao showdown com mão fraca." },
};

const pct = (x: number, d = 1) => `${(x * 100).toFixed(d).replace(".", ",")}%`;
const n1 = (x: number) => x.toFixed(1).replace(".", ",");

/** Frase com o número do spot: risk premium (e bubble factor) do herói contra um adversário. */
export function explainRiskPremium(rp: number, pos: string, bf?: number): string {
  if (rp < -0.005) return `Risk premium de ${pct(rp)} contra o ${pos}: aqui é desconto. O bounty de quem você cobre vale mais do que o risco do ICM, então você pode entrar no all-in com uns ${n1(-rp * 100)} pontos de equity a menos que na conta das fichas.`;
  if (rp < 0.02) return `Risk premium de +${pct(rp)} contra o ${pos}: quase nada. Contra ele você joga praticamente como em fichas (chip EV).`;
  const bfTxt = bf !== undefined && Number.isFinite(bf) ? ` (bubble factor ${n1(bf)}: perder esse all-in custa ${n1(bf)}× o que ganhá-lo acrescenta)` : "";
  return `Risk premium de +${pct(rp)} contra o ${pos}${bfTxt}: para entrar num all-in contra ele você precisa de uns ${n1(rp * 100)} pontos de equity a mais do que a conta das fichas pede. Ex.: se as pot odds pedem 40%, com o ICM você precisa de uns ${n1(40 + rp * 100)}%.`;
}

/** Frase com o número do spot: bounty power e equity drop contra um adversário. */
export function explainBounty(pos: string, bp: number, covers: boolean, drop: number): string {
  const bpTxt = bp >= 1.5 ? "cabeça grande para o stack: eliminar ele rende bastante" : bp >= 0.8 ? "cabeça do tamanho normal para o stack" : "cabeça pequena para o stack: o bounty pesa pouco";
  return covers
    ? `${pos} tem BP ${n1(bp)} (${bpTxt}). Você cobre ele: para pagar o all-in dele, precisa de uns ${n1(drop)} pontos de equity a menos (equity drop), porque ganhando leva o bounty.`
    : `${pos} te cobre: o desconto do bounty é dele (uns ${n1(drop)} pontos, pelo seu BP), não seu. Se você perder, sai do torneio.`;
}

/** Termos citados num texto (explicação da decisão), para a nota com asterisco. Máximo `max`, na ordem do glossário. */
export function termsIn(text: string, max = 3): TermId[] {
  const t = text.toLowerCase();
  const hits: [TermId, RegExp][] = [
    ["risk_premium", /risk premium/], ["bubble_factor", /bubble factor/], ["icm", /\bicm\b/], ["bounty_power", /bounty power|\bbp\b/],
    ["equity_drop", /equity drop|desconto/], ["pot_odds", /pot odds/], ["fold_equity", /fold equity|folda|desiste/], ["nash", /nash|equilíbrio/],
    ["resteal", /resteal/], ["equity", /equity/],
  ];
  return hits.filter(([, re]) => re.test(t)).map(([id]) => id).slice(0, max);
}
