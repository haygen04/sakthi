package com.sakthi.mis.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "fact_production")
public class FactProduction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "fact_id")
    private Long factId;

    @Column(name = "date_key", nullable = false, length = 10)
    private String dateKey;

    @Column(name = "year_week", nullable = false, length = 8)
    private String yearWeek;

    @Column(name = "year_month", nullable = false, length = 7)
    private String yearMonth;

    @Column(name = "shop_id", nullable = false)
    private Integer shopId;

    @Column(name = "shift_id", nullable = false)
    private Integer shiftId;

    @Column(name = "machine_id", nullable = false)
    private Integer machineId;

    @Column(name = "part_id", nullable = false)
    private Integer partId;

    @Column(name = "target_qty")
    private Integer targetQty;

    @Column(name = "produced_qty")
    private Integer producedQty;

    @Column(name = "accepted_qty")
    private Integer acceptedQty;

    @Column(name = "rejected_qty")
    private Integer rejectedQty;

    @Column(name = "rejection_pct", precision = 5, scale = 2)
    private BigDecimal rejectionPct;

    @Column(name = "first_pass_yield_pct", precision = 5, scale = 2)
    private BigDecimal firstPassYieldPct;

    @Column(name = "gross_weight_kg", precision = 12, scale = 2)
    private BigDecimal grossWeightKg;

    public FactProduction() {}

    public Long getFactId() { return factId; }
    public void setFactId(Long factId) { this.factId = factId; }

    public String getDateKey() { return dateKey; }
    public void setDateKey(String dateKey) { this.dateKey = dateKey; }

    public String getYearWeek() { return yearWeek; }
    public void setYearWeek(String yearWeek) { this.yearWeek = yearWeek; }

    public String getYearMonth() { return yearMonth; }
    public void setYearMonth(String yearMonth) { this.yearMonth = yearMonth; }

    public Integer getShopId() { return shopId; }
    public void setShopId(Integer shopId) { this.shopId = shopId; }

    public Integer getShiftId() { return shiftId; }
    public void setShiftId(Integer shiftId) { this.shiftId = shiftId; }

    public Integer getMachineId() { return machineId; }
    public void setMachineId(Integer machineId) { this.machineId = machineId; }

    public Integer getPartId() { return partId; }
    public void setPartId(Integer partId) { this.partId = partId; }

    public Integer getTargetQty() { return targetQty; }
    public void setTargetQty(Integer targetQty) { this.targetQty = targetQty; }

    public Integer getProducedQty() { return producedQty; }
    public void setProducedQty(Integer producedQty) { this.producedQty = producedQty; }

    public Integer getAcceptedQty() { return acceptedQty; }
    public void setAcceptedQty(Integer acceptedQty) { this.acceptedQty = acceptedQty; }

    public Integer getRejectedQty() { return rejectedQty; }
    public void setRejectedQty(Integer rejectedQty) { this.rejectedQty = rejectedQty; }

    public BigDecimal getRejectionPct() { return rejectionPct; }
    public void setRejectionPct(BigDecimal rejectionPct) { this.rejectionPct = rejectionPct; }

    public BigDecimal getFirstPassYieldPct() { return firstPassYieldPct; }
    public void setFirstPassYieldPct(BigDecimal firstPassYieldPct) { this.firstPassYieldPct = firstPassYieldPct; }

    public BigDecimal getGrossWeightKg() { return grossWeightKg; }
    public void setGrossWeightKg(BigDecimal grossWeightKg) { this.grossWeightKg = grossWeightKg; }
}
