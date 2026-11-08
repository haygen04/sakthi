package com.sakthi.mis.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "fact_rejection")
public class FactRejection {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "fact_rejection_id")
    private Long factRejectionId;

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

    @Column(name = "defect_id", nullable = false)
    private Integer defectId;

    @Column(name = "rejected_qty", nullable = false)
    private Integer rejectedQty;

    @Column(name = "scrap_qty", nullable = false)
    private Integer scrapQty;

    @Column(name = "reworkable_qty", nullable = false)
    private Integer reworkableQty;

    @Column(name = "scrap_cost", precision = 12, scale = 2)
    private BigDecimal scrapCost;

    public FactRejection() {}

    public Long getFactRejectionId() { return factRejectionId; }
    public void setFactRejectionId(Long factRejectionId) { this.factRejectionId = factRejectionId; }

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

    public Integer getDefectId() { return defectId; }
    public void setDefectId(Integer defectId) { this.defectId = defectId; }

    public Integer getRejectedQty() { return rejectedQty; }
    public void setRejectedQty(Integer rejectedQty) { this.rejectedQty = rejectedQty; }

    public Integer getScrapQty() { return scrapQty; }
    public void setScrapQty(Integer scrapQty) { this.scrapQty = scrapQty; }

    public Integer getReworkableQty() { return reworkableQty; }
    public void setReworkableQty(Integer reworkableQty) { this.reworkableQty = reworkableQty; }

    public BigDecimal getScrapCost() { return scrapCost; }
    public void setScrapCost(BigDecimal scrapCost) { this.scrapCost = scrapCost; }
}

