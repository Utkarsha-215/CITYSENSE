# Technical Specification: Medallion Transformations & KPI Formulas

---

## 1. Deduplication & Lineage Strategy

In distributed data pipelines, raw streams frequently receive overlapping or redelivered batches.
The **Bronze-to-Silver** layer enforces strict idempotence:
- **Traffic Deduplication Key**: `(sensor_id, timestamp)`
- **Weather Deduplication Key**: `(city, timestamp)`
- **Tie-Breaking Rule**: The record with the latest `ingested_at` timestamp is preserved; earlier duplicate records are dropped.

---

## 2. Spatiotemporal Cross-Domain Alignment

Because traffic sensors sample at continuous irregular intervals (e.g., every 15–60 seconds) while weather observation stations report at discrete hourly intervals, spatial and temporal alignment is performed via:

$$\text{observation\_hour} = \text{floor}_{\text{hour}}(\text{timestamp}_{\text{traffic}})$$

$$\text{Weather Record} = \sigma_{\text{timestamp} = \text{observation\_hour}}(\text{Weather Silver})$$

The resulting joined relation guarantees that each sensor reading is enriched with the exact meteorological conditions active during that specific clock hour.

---

## 3. Smart City Mobility KPI Mathematical Definitions

### A. Speed Deficit Ratio
Quantifies the normalized velocity drop relative to legal corridor design capacity:

$$\text{speed\_deficit\_ratio} = \max\left(0.0, \; \frac{v_{\text{limit}} - v_{\text{avg}}}{v_{\text{limit}}}\right)$$

- When $v_{\text{avg}} \ge v_{\text{limit}}$, $\text{speed\_deficit\_ratio} = 0.0$ (free flow).
- When $v_{\text{avg}} = 0$, $\text{speed\_deficit\_ratio} = 1.0$ (gridlock).

### B. Composite Mobility Congestion Score
Standardizes multi-factor congestion into a bounded index $[0.0, 100.0]$:

$$\text{congestion\_score} = \min\left(100.0, \; \max\left(0.0, \; 0.5 \cdot \text{road\_occupancy\_pct} + 0.5 \cdot (\text{speed\_deficit\_ratio} \times 100)\right)\right)$$

### C. Weather Disruption Indicator
Binary classifier flagging conditions where meteorological hazards degrade urban mobility:

$$\text{is\_weather\_disrupted} = \begin{cases} 
\text{True} & \text{if } \text{rainfall\_mm} > 1.0 \lor \text{wind\_speed\_kmh} > 30.0 \\ 
\text{False} & \text{otherwise} 
\end{cases}$$

### D. Estimated Hourly Throughput
Projects the realistic hourly vehicle carrying capacity factoring in corridor speed degradation:

$$\text{throughput} = \left\lfloor \text{vehicle\_count} \times \text{clip}\left(\frac{v_{\text{avg}}}{v_{\text{limit}}}, 0.1, 1.2\right) \right\rceil$$
