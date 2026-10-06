MEMORANDUM

**TO:** Ritu Deshpande, Head of D2C Operations  
**CC:** Farhan Sheikh, Finance Controller; Meenal Joshi, Service Desk Manager; Tanmay Kulkarni, Data & IT Admin  
**FROM:** Returns-Risk Project Team, on behalf of Kabir Nanda, Account Lead  
**DATE:** 6 October 2026  
**SUBJECT:** Returns model: a recommendation to call high-risk orders instead of holding them

---

## Summary
Thank you to Tanmay for preparing the data. We have built a tool that scores every order before dispatch. Based on the results, we recommend that Kestrel phone the riskiest 25% of orders to confirm them, ship all other orders as normal, and not hold any orders. The tool runs on Kestrel's own computers and costs nothing per order.

## About the 95% accuracy target
We looked closely at this target and would like to suggest a more useful measure. A simple rule that predicts "no order will be returned" is already 89% accurate, but it saves no money. The only version that reached 99% used information recorded after a product had already come back, so it cannot work at dispatch. When tested with dispatch-time data, it did worse than the tool we are recommending. A clearer number for the board would be:

> For every 100 orders we call, about 27 would otherwise have been returned, compared with about 11 in every 100 orders today. By calling just 1 in 4 orders, we reach the orders behind 6 out of every 10 returns.

We would also like to be clear about the tool's limits. About 3 in 4 calls will reach customers who would have kept their order, which is acceptable at ₹45 per call. About 4 in 10 returns will not be flagged and will be handled as they are today. All results come from months the tool had not seen before, including a final three months that were kept aside and checked only once.

## Financial impact
At the volume in the data provided (about 700 orders a month), returns cost about ₹90,000 a month (78 returns × ₹1,150, the figure Finance uses).

| Option | Orders actioned | Returns avoided | Good orders lost | Net per month |
|---|--:|--:|--:|--:|
| Hold riskiest 10% (current proposal) | ~70 held | ~3 | ~5 cancelled | −₹10,400 |
| Call riskiest 25% (recommended) | ~175 called (~6/day) | ~17 (1 in 5) | None | +₹11,400 |

Holding orders loses money because about 12% of held customers cancel, and most of them are good customers buying expensive items such as robot vacuums and water purifiers. Calling saves about 13% of the monthly return cost, or ₹16,300 per 1,000 orders, so the saving grows with actual order volume. These figures are conservative, as they do not include the profit kept when a return is prevented. At your estimate of ₹600 per return, calling still pays, though less: about ₹2,900 a month when calling the riskiest 15%.

## Shield customers
Shield members place 22% of orders but account for 36% of returns, so they return about twice as often as other customers, probably because returns are free for them. About 4 in 10 calls will go to Shield members, and a call does not put their order at risk, which is one more reason to call rather than hold.

## Suggested next steps
1. **Start a small, fair test.** Each day, call a random half of the flagged orders and ship the other half without a call, then compare return rates after 30 days. About 300 orders are needed in each group (around three months at the current data volume, sooner at full volume). If calls reduce returns by more than 15%, a full roll-out would make sense; below that, the calls would not pay for themselves.
2. **Agree call capacity with Meenal's team:** about 3 calls a day during the test and about 6 at full roll-out. If fewer agents are available, calling only the riskiest 10% still captures 73% of the value.
3. **Three data improvements, if Tanmay is able to help:** keep each order's service status as it was at dispatch, record Shield status as of the order date, and correct the October 2025 order values that were stored in paise.
4. **Hold no orders** until the test results are available.
