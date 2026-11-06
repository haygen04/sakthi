package com.sakthi.mis.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "dim_defect")
public class DimDefect {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "defect_id")
    private Integer defectId;

    @Column(name = "defect_code", nullable = false, unique = true, length = 32)
    private String defectCode;

    @Column(name = "defect_name", nullable = false, length = 128)
    private String defectName;

    @Column(name = "category", nullable = false, length = 64)
    private String category;

    @Column(name = "standard_cost", precision = 12, scale = 2)
    private BigDecimal standardCost;

    public DimDefect() {}

    public Integer getDefectId() { return defectId; }
    public void setDefectId(Integer defectId) { this.defectId = defectId; }

    public String getDefectCode() { return defectCode; }
    public void setDefectCode(String defectCode) { this.defectCode = defectCode; }

    public String getDefectName() { return defectName; }
    public void setDefectName(String defectName) { this.defectName = defectName; }

    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }

    public BigDecimal getStandardCost() { return standardCost; }
    public void setStandardCost(BigDecimal standardCost) { this.standardCost = standardCost; }
}
