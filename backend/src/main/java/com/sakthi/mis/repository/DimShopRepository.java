package com.sakthi.mis.repository;

import com.sakthi.mis.entity.DimShop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface DimShopRepository extends JpaRepository<DimShop, Integer> {
    Optional<DimShop> findByShopCode(String shopCode);
}

