import {pathToFileURL} from 'node:url';
const {evaluatePostflopSpot:run,calculateExactOutsEquityPct:outs}=await import(pathToFileURL(process.argv[2]).href);
const base={street:'flop',potBB:10,effectiveStackBB:60,heroPosition:'IP',playersInPot:2,
    preflopInitiative:'hero_pfr',boardTexture:'wet_connected',turnRiverCard:'brick',
    handCategory:'strong_value',drawOuts:0,villainAction:'checked_to_hero',villainLine:'uncapped',
    blockerType:'none',aggressionProfile:'balanced',bountyCoverBB:0,hudSampleHands:0,hudFoldToCbet:0,
    useMixedRng:true,rngRoll:99};
const cases:any[]=[];
const mix=run(base);
cases.push({id:'mixed_line_does_not_change_executable_fields',input:base,
    expected:'Secondary Check must resolve to structured CHECK with zero size before any executor.',
    actual:{action:mix.action,size:mix.sizingBB,rngExecutedLine:mix.rngExecutedLine,frequencies:mix.frequencies},
    satisfies:mix.action==='CHECK'&&mix.sizingBB===0});
const cheap=run({...base,street:'river',potBB:100,effectiveStackBB:2,handCategory:'medium_showdown',
    boardTexture:'dry_high',villainAction:'facing_shove',useMixedRng:false});
cases.push({id:'cheap_shove_folds_despite_own_equity',
    expected:'Call when the engines own equity is above its required price for the closing call.',
    actual:{action:cheap.action,rawEquity:cheap.rawEquityPct,effectiveEquity:cheap.effectiveEquityPct,
        requiredEquity:cheap.requiredEquityPct,sizingLabel:cheap.sizingLabel,streetPlan:cheap.streetPlan},
    satisfies:cheap.action==='CALL'});
const allInInput={...base,street:'turn',potBB:10,effectiveStackBB:10,handCategory:'nut_draw',drawOuts:9,
    villainAction:'facing_shove',useMixedRng:false};
const ip=run({...allInInput,heroPosition:'IP'}),oop=run({...allInInput,heroPosition:'OOP'});
cases.push({id:'all_in_realization_should_not_depend_on_position',input:allInInput,
    expected:'Same category/range assumptions and no future betting: EQR=1 for both positions.',
    actual:{ip:{action:ip.action,equity:ip.effectiveEquityPct,eqr:ip.eqrFactor},
        oop:{action:oop.action,equity:oop.effectiveEquityPct,eqr:oop.eqrFactor}},
    satisfies:ip.effectiveEquityPct===oop.effectiveEquityPct});
const raise=run({...base,potBB:10,effectiveStackBB:100,handCategory:'nut_value',villainAction:'facing_large_bet',useMixedRng:false});
cases.push({id:'raise_size_requires_an_explicit_semantic_contract',
    expected:'If sizingBB is raise-to, it must reach at least 15BB over the internally modeled 7.5BB bet.',
    actual:{action:raise.action,sizingBB:raise.sizingBB,sizingLabel:raise.sizingLabel,min_raise_to_bb_under_stated_assumption:15},
    assumption:'This is a future executor contract failure: current TypeScript returns no raise-to versus raise-by type.',
    satisfies:raise.sizingBB>=15});
console.log(JSON.stringify({scope:'Pure TypeScript synthetic/manual inputs; no browser, OCR, input or Gemini API call.',
    cases,violations:cases.filter(x=>!x.satisfies).length,
    outs_example:{function_result:outs(9,'turn','dry_high'),unrounded_next_card_probability_pct:100*9/46}},null,2));
