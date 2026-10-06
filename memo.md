# Returns: call the risky orders, don't hold them

**To:** Ritu Deshpande, Head of D2C Operations · **Cc:** Farhan Sheikh, Meenal Joshi, Tanmay Kulkarni  
**From:** Returns-risk project team (via Kabir Nanda) · **Date:** 6 October 2026  
**Subject:** Returns model: call the risky orders before dispatch; don't hold them

## The decision
Score every order before dispatch. **Phone the riskiest quarter of orders to confirm them, and ship everything else as normal. Don't hold any order.** The tool is built, runs on Kestrel's own computers, and costs nothing per order.

## The number for the board
"95% accuracy" isn't a target we can honestly hit, and it wouldn't tell you much. Saying "no order will be returned" is already 89% accurate and saves nothing. The only version that reached 99% was reading information filled in *after* a product came back; used at dispatch, it did worse than our tool. The number that matters:

> **Of the orders we call, about 1 in 4 would otherwise come back, 2.4 times the normal rate. And that quarter of orders holds 6 in 10 of all returns.**

About 3 in 4 calls will reach customers who would have kept the order anyway. At ₹45 a call that's fine, and it's exactly why holding those orders is costly. About 4 in 10 returns won't be flagged; they're handled as today.

We tested this on months the tool had never seen, including a final three months we kept aside and checked only once.

## The rupees
At the volume in the data Tanmay sent (~700 orders a month), returns cost about **₹90,000 a month** (~78 returns × ₹1,150, Finance's figure).

| | Calls or holds | Returns avoided | Good orders lost | Net per month |
|---|---|---|---|---|
| **Hold the riskiest 10%** (the original plan) | ~70 holds | ~3 | ~5 cancelled | **−₹10,400** |
| **Call the riskiest 25%** (recommended) | ~175 calls (~6 a day) | ~17 (1 in 5) | none | **+₹11,400** |

Holding loses money: 12% of held customers cancel, and the riskiest orders are often expensive vacuums and purifiers. Calling saves about **13% of the monthly return cost**, or **₹16,300 per 1,000 orders**, so it grows with your real volume. These figures are deliberately conservative. At your ₹600-per-return figure it still pays, on a smaller scale: about ₹2,900 a month calling the riskiest 15%.

## Shield customers
Shield members are 22% of orders but 36% of returns, twice the normal rate, since returns are free for them; about 4 in 10 calls will go to them. A call never puts their order at risk, one more reason not to hold.

## What to do next week
1. **Agree call capacity** with Meenal's desk: start at ~6 calls a day (the riskiest 25%), or the riskiest 10% if fewer agents are free. During the step-2 test it's ~3 a day, since only half the flagged orders are called. Calling the top 10% already earns 73% of the value.
2. **Start a fair test, not a full roll-out.** The 35% figure from the spring call pilot is the one number we had to assume. Each day, call a random half of the flagged orders and ship the other half untouched, then compare their return rates 30 days later. It needs ~300 orders in each half (about 3 months at this volume, sooner at full volume). Roll out if calls cut returns by more than ~15%; below that they don't pay.
3. **Ask Tanmay for three data fixes:** keep each order's service status *as it was at dispatch*; record Shield status *as of the order date*; correct the October 2025 order values stored in paise.
4. **Hold no orders** in the meantime.

*Detail: `evidence/backtest_report.md`. The tool starts with three commands from the README.*
