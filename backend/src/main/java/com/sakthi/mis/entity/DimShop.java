package com.sakthi.mis.entity;

import jakarta.persistence.*;

@Entity
@Table(name = "dim_shop")
public class DimShop {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "shop_id")
    private Integer shopId;

    @Column(name = "shop_code", nullable = false, unique = true, length = 32)
    private String shopCode;

    @Column(name = "shop_name", nullable = false, length = 128)
    private String shopName;

    @Column(name = "division_name", nullable = false, length = 64)
    private String divisionName;

    public DimShop() {}

    public Integer getShopId() { return shopId; }
    public void setShopId(Integer shopId) { this.shopId = shopId; }

    public String getShopCode() { return shopCode; }
    public void setShopCode(String shopCode) { this.shopCode = shopCode; }

    public String getShopName() { return shopName; }
    public void setShopName(String shopName) { this.shopName = shopName; }

    public String getDivisionName() { return divisionName; }
    public void setDivisionName(String divisionName) { this.divisionName = divisionName; }
}
