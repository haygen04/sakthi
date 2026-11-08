package com.sakthi.mis.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.sql.Timestamp;

@Entity
@Table(name = "report_runs")
public class ReportRun {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "run_id")
    private Long runId;

    @Column(name = "report_type", nullable = false, length = 64)
    private String reportType;

    @Column(name = "period_key", nullable = false, length = 32)
    private String periodKey;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "excel_path", length = 512)
    private String excelPath;

    @Column(name = "pdf_path", length = 512)
    private String pdfPath;

    @Column(name = "total_produced")
    private Integer totalProduced;

    @Column(name = "total_rejected")
    private Integer totalRejected;

    @Column(name = "rejection_pct", precision = 5, scale = 2)
    private BigDecimal rejectionPct;

    @Column(name = "generated_by", length = 64)
    private String generatedBy;

    @Column(name = "run_duration_ms")
    private Integer runDurationMs;

    @Column(name = "error_message", length = 1024)
    private String errorMessage;

    @Column(name = "created_at")
    private Timestamp createdAt;

    public ReportRun() {}

    public Long getRunId() { return runId; }
    public void setRunId(Long runId) { this.runId = runId; }

    public String getReportType() { return reportType; }
    public void setReportType(String reportType) { this.reportType = reportType; }

    public String getPeriodKey() { return periodKey; }
    public void setPeriodKey(String periodKey) { this.periodKey = periodKey; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getExcelPath() { return excelPath; }
    public void setExcelPath(String excelPath) { this.excelPath = excelPath; }

    public String getPdfPath() { return pdfPath; }
    public void setPdfPath(String pdfPath) { this.pdfPath = pdfPath; }

    public Integer getTotalProduced() { return totalProduced; }
    public void setTotalProduced(Integer totalProduced) { this.totalProduced = totalProduced; }

    public Integer getTotalRejected() { return totalRejected; }
    public void setTotalRejected(Integer totalRejected) { this.totalRejected = totalRejected; }

    public BigDecimal getRejectionPct() { return rejectionPct; }
    public void setRejectionPct(BigDecimal rejectionPct) { this.rejectionPct = rejectionPct; }

    public String getGeneratedBy() { return generatedBy; }
    public void setGeneratedBy(String generatedBy) { this.generatedBy = generatedBy; }

    public Integer getRunDurationMs() { return runDurationMs; }
    public void setRunDurationMs(Integer runDurationMs) { this.runDurationMs = runDurationMs; }

    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    public Timestamp getCreatedAt() { return createdAt; }
    public void setCreatedAt(Timestamp createdAt) { this.createdAt = createdAt; }
}

