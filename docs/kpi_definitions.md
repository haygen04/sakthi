# KPI Definitions: Manufacturing MIS & Rejection Reports

This document establishes the official formula standards, business logic, aggregation rules, and alerting thresholds used by the Automated Manufacturing MIS and Rejection Report Generator.

---

## 1. Core Production & Quality KPIs

### 1.1 Total Production Quantity ($Q_{prod}$)
$$\text{Production Qty} = \sum \text{produced\_qty}$$
- **Foundry Scope:** Total gross castings poured / knocked out.
- **Machine Shop Scope:** Total components fully processed through designated machine operations.

### 1.2 Target Adherence / Production Efficiency (%)
$$\text{Production Efficiency \%} = \left( \frac{\sum \text{produced\_qty}}{\sum \text{target\_qty}} \right) \times 100$$
- **Benchmark:** $\ge 95.0\%$ is Good; $90.0\% - 94.9\%$ is Watch; $< 90.0\%$ is Unacceptable.

### 1.3 Total Rejection Quantity ($Q_{rej}$)
$$\text{Total Rejection Qty} = \sum \text{rejected\_qty}$$
- Constitutes all parts failing visual, dimensional, ultrasonic, MPI, or metallurgical checks.

### 1.4 Rejection Percentage ($\text{Rej \%}$)
$$\text{Rejection \%} = \left( \frac{\sum \text{rejected\_qty}}{\sum \text{produced\_qty}} \right) \times 100$$
- **Foundry Thresholds:**
  - **Good (Pastel Mint):** $\le 3.0\%$
  - **Watch / Warn (Pastel Butter):** $3.1\% - 4.5\%$
  - **Bad / Critical (Pastel Rose):** $> 4.5\%$
- **Machine Shop Thresholds:**
  - **Good:** $\le 1.8\%$
  - **Watch / Warn:** $1.9\% - 2.8\%$
  - **Bad / Critical:** $> 2.8\%$

### 1.5 First-Pass Yield (FPY %)
$$\text{FPY \%} = 100 - \text{Rejection \%} = \left( \frac{\sum \text{accepted\_qty}}{\sum \text{produced\_qty}} \right) \times 100$$
- Indicator of process stability without secondary rework.

### 1.6 Scrap vs Rework Ratio
$$\text{Scrap Ratio \%} = \left( \frac{\sum \text{scrap\_qty}}{\sum \text{rejected\_qty}} \right) \times 100$$
$$\text{Rework Ratio \%} = \left( \frac{\sum \text{reworkable\_qty}}{\sum \text{rejected\_qty}} \right) \times 100$$

---

## 2. Multidimensional Breakdown Metrics

### 2.1 Shop-wise Distribution
- **Foundry MIS:**
  - Liquid metal melted (MT)
  - Castings poured vs good castings
  - Yield % = $(\text{Good Casting Weight} / \text{Liquid Metal Poured}) \times 100$
- **Machine Shop MIS:**
  - Component machining output
  - Rejection split by Machining vs Incoming Raw Casting Defect

### 2.2 Shift-wise Variance
- Shift A (06:00 - 14:00) vs Shift B (14:00 - 22:00) vs Shift C (22:00 - 06:00)
- Identifies operational shifts with abnormal rejection spikes or lower operator efficiency.

### 2.3 Part-wise Rejection Contribution
- Identifies critical high-runner parts with disproportionate defect counts:
$$\text{Part Rejection Contribution \%} = \left( \frac{\text{Part Rejected Qty}}{\text{Total Rejected Qty in Period}} \right) \times 100$$

### 2.4 Machine-wise Quality Analysis
- Evaluates individual CNC/VMC lines, molding lines, and pouring stations:
$$\text{Machine Rejection \%} = \left( \frac{\text{Machine Rejected Qty}}{\text{Machine Produced Qty}} \right) \times 100$$

---

## 3. Defect Pareto & Trend Analysis

### 3.1 Defect Pareto (80/20 Rule)
- Defect causes ranked in descending order of rejection quantity.
- Cumulative Defect Percentage:
$$\text{Cumulative \%}_k = \left( \frac{\sum_{i=1}^k \text{Defect Qty}_i}{\sum_{all} \text{Defect Qty}} \right) \times 100$$
- Highlights the vital 2-3 defect categories causing $80\%$ of plant losses.

### 3.2 Week-on-Week (WoW) Delta
$$\Delta \text{WoW Rej \%} = \text{Rejection \%}_{\text{Current Week}} - \text{Rejection \%}_{\text{Previous Week}}$$
- Positive delta $\implies$ deterioration (Rose status chip).
- Negative delta $\implies$ improvement (Mint status chip).

### 3.3 Month-on-Month (MoM) Delta
$$\Delta \text{MoM Rej \%} = \text{Rejection \%}_{\text{Current Month}} - \text{Rejection \%}_{\text{Previous Month}}$$

### 3.4 Cost of Rejection (COP - Cost of Poor Quality)
$$\text{Rejection Cost} = \sum (\text{scrap\_qty} \times \text{standard\_cost}) + \sum (\text{reworkable\_qty} \times \text{rework\_cost})$$
- Quantifies financial impact for executive review.

---

## 4. Anomaly Rules & Auto-Generated Commentary Triggers

The system automatically generates executive bullet points in the reports when:
1. **Critical Defect Dominance:** A single defect accounts for $> 35\%$ of total rejections.
2. **Shop Spike:** Any shop experiences WoW rejection increase $> +0.5\%$.
3. **Part Outlier:** Any individual part's rejection rate exceeds $2\times$ the shop average.
4. **Machine Deterioration:** Machine tool wear / repetitive failure crossing preset control limits.

