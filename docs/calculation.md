# calculation.md — The math, explained simply

Every number SignalBridge shows comes from one of the small formulas below.
They are all plain arithmetic — no AI, no magic. You can check them by hand.

Two ground rules used everywhere:
- **Quantities are whole units** (you can't have 1.5 jackets).
- **Money is stored in paise** (integer "minor units"), so ₹1,800 is `180000`.
  We only divide by 100 when we show it on screen.

We use one running example the whole way: **blue jackets at the Mumbai DC**.

---

## The setup (our dummy data)

| Thing | Value |
|---|---|
| On-hand stock at Mumbai (`WH-MUM`) | **120** units |
| Incoming shipment `SHP-001` | **500** units |
| …normally arrives | 12 Oct (in time) |
| …but port is delayed, so now arrives | 19 Oct (too late) |
| Customer order `LINE-001` | **200** units due **16 Oct** |
| Spare stock in Pune dark store | **20** units free |
| Jacket sell price | ₹2,499 (`249900` paise) |
| Supplier A offer | 90 units @ ₹1,800 + ₹5,000 shipping, arrives 15 Oct |
| VIP late penalty | ₹50,000 (`5000000` paise) |

---

## 1. Exposure — "how many units short?"

This is the most important formula. We always measure **against a deadline**.

```
supply  = on_hand + incoming that arrives on/before the deadline
demand  = open orders due on/before the deadline
shortage = max(0, demand − supply)
```

`max(0, …)` just means "a shortage can't be negative" — if we have enough, the
shortage is 0.

### Normal day (nothing wrong)

The 500 units arrive 12 Oct, before the 16 Oct deadline, so they **count**:

```
supply  = 120 + 500 = 620
demand  = 200
shortage = max(0, 200 − 620) = 0      ✅ no problem
```

### After the port delay

Now the 500 units arrive 19 Oct — **after** the deadline — so they **don't count**:

```
supply  = 120 + 0 = 120
demand  = 200
shortage = max(0, 200 − 120) = 80     ⚠️ short 80 units
```

> The delay didn't destroy any stock. It just moved the 500 units from "arrives
> in time" to "arrives too late". That one change creates the 80-unit shortage.

*(Code: `backend/domain/exposure.py`)*

---

## 2. Internal balancing — "use our own stock first"

Before buying from anyone, check our other warehouses and dark stores for **free**
stock. Free means not already promised to someone else:

```
free = on_hand − reserved
```

Pune dark store has 20 on hand, 0 reserved → **20 free**.

```
used from internal = min(shortage, internal_free) = min(80, 20) = 20
remainder to buy    = shortage − used = 80 − 20 = 60
```

So we still need **60** units from outside.

*(Code: `backend/domain/network_balance.py`)*

---

## 3. Supplier choice — "buy the remaining 60 cheaply"

An offer is **usable** only if it has enough stock **and** arrives by the deadline.

| Offer | Stock | Arrives | Enough for 60? | In time (by 16 Oct)? | Usable? |
|---|---|---|---|---|---|
| A | 90 | 15 Oct | yes | yes | ✅ |
| B | 30 | 14 Oct | no (only 30) | yes | ❌ |
| C | 200 | 20 Oct | yes | no (too late) | ❌ |

Only **A** works. Its cost for 60 units:

```
cost = (units × unit_price) + shipping
     = (60 × 180000) + 500000
     = 10800000 + 500000
     = 11300000 paise   =  ₹1,13,000
```

*(Code: `backend/domain/planner.py`)*

---

## 4. Margin check — "is the fix worth it?"

Don't spend more than you save. We compare the cost against what we protect.

```
protected_revenue = shortage × sell_price = 80 × 249900 = 19992000   (₹1,99,920)
penalty_avoided   = 5000000                                           (₹50,000)
net_benefit       = protected_revenue + penalty_avoided − recovery_cost
                  = 19992000 + 5000000 − 11300000
                  = 13692000                                          (₹1,36,920)
```

`net_benefit` is positive → **verdict: worth_it** ✅

If the cost had been *higher* than what we protect, `net_benefit` would be
negative and the verdict would be **not_worth_it** (don't do it).

*(Code: `backend/domain/margin.py`)*

---

## 5. Surplus forecast — "will we be overstocked later?"

We bought replacements. But the delayed shipment of 500 is **still coming** — it
just arrives late. When it lands, some of it is now extra:

```
expected_surplus = min(late_shipment_units, units_we_recovered)
                 = min(500, 80)
                 = 80 units of likely overstock  → suggest a markdown
```

Flagging this early lets you plan a markdown or return instead of being surprised.

*(Code: `backend/domain/surplus.py`)*

---

## 6. Governance — "who has to approve it?"

The approval level depends on how much money the plan spends. Thresholds are in
paise (`backend/core/config.py`):

| Recovery cost | Tier |
|---|---|
| ≤ ₹50,000 (`5000000`) | local planner |
| ≤ ₹5,00,000 (`50000000`) | regional manager |
| above that | executive |

Our cost is ₹1,13,000, which is above ₹50,000 but below ₹5,00,000 →
**regional manager**.

*(Code: `backend/domain/governance.py`)*

---

## The whole example on one line

```
80 short  →  20 from our own stock  →  buy 60 from Supplier A for ₹1,13,000
          →  worth it (protects ₹1,99,920 + ₹50,000 penalty)
          →  warn: 80 units future surplus (markdown)
          →  needs regional-manager approval
```

Run `python -m scripts.demo` and you'll see these exact numbers printed.
