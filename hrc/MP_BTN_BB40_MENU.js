/* Original tree-menu script for the Software study. NOT a solver or strategy.
 * API: https://www.holdemresources.net/docs/scripting/
 * Stable HRC player indices come from the parent hand (nine dealt players).
 * Configure stacks, antes, prizes, bounties and parent ranges in HRC itself.
 * No hand is forced to bet/fold by this script; HRC calculates frequencies.
 */
var POSTFLOP_BETS = [1 / 3, 1 / 2, 2 / 3, 1];
var POSTFLOP_RAISES = [1];
var MAX_POSTFLOP_BETS = 3;

function uniqueSizes(values) {
    var result = [];
    for (var i = 0; i < values.length; i++) {
        var value = Number(values[i]);
        if (result.indexOf(value) < 0) result.push(value);
    }
    return result;
}

function preflopWithAllIn(ctx, sizing) {
    // HRC may return a Java long[], without JavaScript concat methods.
    var values = uniqueSizes(ctx.sizingsPreflop(sizing));
    values.push(ctx.sizingAllIn());
    return uniqueSizes(values);
}

function getSizingsPreflop(ctx) {
    // This broad menu preserves possible alternatives in a NEW parent hand.
    // It does not recreate or lock the supplied NVT ranges by itself.
    var bets = ctx.getBetCount();
    if (bets <= 1) return [ctx.sizingBigBlinds(2), ctx.sizingAllIn()];
    if (bets === 2) return preflopWithAllIn(ctx, '3x + 1x');
    if (bets === 3) return preflopWithAllIn(ctx, '2.2x');
    return [ctx.sizingAllIn()];
}

function canFlatCallPreflop(ctx) {
    // Includes BTN flat and BB OVERCALL. The target line is selected in HRC.
    return true;
}

function getSizingsPostflop(ctx) {
    if (ctx.getBetCount() >= MAX_POSTFLOP_BETS) return [];
    var fractions = ctx.getBetCount() === 0 ? POSTFLOP_BETS : POSTFLOP_RAISES;
    var sizes = fractions.map(function (fraction) { return ctx.sizingPot(fraction); });
    return uniqueSizes(sizes.concat([ctx.sizingAllIn()]));
}

function canFlatCallPostflop(ctx) {
    return true;
}

function hasNextStreetBetting(ctx) {
    return true; // Three-player betting may continue through the river.
}
