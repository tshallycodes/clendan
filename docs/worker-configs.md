# Clendan — AI Worker Configuration Reference (Sourced)

> All monetary values in **integer minor units** (cents/pence). `10000` = $100.00 / £100.00.  
> Percentages stored as decimal `0.0–1.0` unless noted as basis points (bps).  
> ⚠️ = commonly misconfigured in practice. 📌 = regulatory requirement with legal consequences.  
> Sources listed per worker; full bibliography at the end.

---

## 1. Invoice Processing

**Context:** Billing schemes — fake, inflated, and duplicate invoices — appear in 86% of asset misappropriation cases and produce a median loss of $145,000 per incident (ACFE, *Report to the Nations 2024*). Three-way matching is the primary control.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `auto_approve_threshold` | int (minor units) | `50000` ($500) | `0 – 500000` | Invoices below this with a clean PO match are auto-approved. Industry guidance: apply full 3-way matching for invoices over $5,000; simpler checks below. [Ramp/Tipalti] ⚠️ |
| `po_match_required` | bool | `true` | — | Make POs mandatory for all goods purchases above a defined floor (typically $500–$1,000). [NetSuite AP guide] Disabling is the #1 control gap in AP fraud. ⚠️ |
| `po_tolerance_pct` | float (0–1) | `0.03` | `0.01 – 0.10` | Letting AP approve within 2–3% of PO amount "can slash processing delays while maintaining proper controls." [Klippa 3-way match guide] Beyond 5% should escalate. |
| `po_tolerance_abs` | int (minor units) | `500` ($5) | `0 – 1000` | Absolute floor: don't flag rounding differences below this. [Klippa] Use OR logic with `po_tolerance_pct`. |
| `duplicate_window_days` | int | `90` | `30 – 365` | Look-back window for duplicate fingerprinting. Vendors occasionally resubmit after 60 days; 90 days catches most. |
| `duplicate_match_fields` | string[] | `["vendor_id","amount","invoice_number"]` | — | Core deduplication fields. Adding `invoice_date` reduces true positives but can miss date-forged re-submissions. |
| `max_invoice_age_days` | int | `180` | `30 – 730` | Reject invoices older than this. Stale invoices are a classic backdating fraud vector. ⚠️ |
| `new_vendor_flag_enabled` | bool | `true` | — | Flag invoices from first-seen vendors. ACFE: new vendor shell companies are a top billing scheme. |
| `new_vendor_hold_days` | int | `3` | `1 – 14` | Hold new-vendor invoices for manual review before releasing to payment. |
| `approval_tier_1_limit` | int (minor units) | `100000` ($1,000) | — | Invoices above `auto_approve_threshold` and below this go to Tier 1 approver. |
| `approval_tier_2_limit` | int (minor units) | `1000000` ($10,000) | — | Above this escalates to finance manager. |
| `approval_tier_3_limit` | int (minor units) | `10000000` ($100,000) | — | Above this requires CFO sign-off. |
| `tax_validation_enabled` | bool | `true` | — | Validate tax amounts against the applicable rate for vendor jurisdiction. |
| `payment_terms_default_days` | int | `30` | `7 – 90` | Default net payment terms when not stated on invoice. Net-30 is industry standard. |
| `blocked_vendor_auto_reject` | bool | `true` | — | Immediately reject invoices from vendors on the blocked list. |
| `ocr_confidence_min` | float (0–1) | `0.85` | `0.70 – 0.99` | Minimum OCR confidence for auto-processing scanned invoices; below this triggers manual entry. |

**Correction from v1:** `po_tolerance_pct` default reduced from 5% to 3% to match published guidance. `auto_approve_threshold` raised from $250 to $500 to align with the $500–$1,000 PO mandatory floor cited in industry sources.

**Sources:** ACFE *Report to the Nations 2024*; Ramp AP 3-way match guide; Klippa 3-way invoice matching guide; Tipalti 3-way match explainer.

---

## 2. AI Accountant

**Context:** No specific regulatory benchmarks exist for ML categorisation confidence thresholds; these remain engineering judgements. Values below reflect operational best practice from accounting automation literature.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `auto_categorise_confidence_min` | float (0–1) | `0.90` | `0.75 – 0.99` | Below this, route to human review. Setting too low (0.60–0.70) silently misfills books. ⚠️ |
| `human_review_confidence_min` | float (0–1) | `0.70` | `0.50 – 0.85` | Below this, flag as uncertain rather than guessing. |
| `learn_from_corrections` | bool | `true` | — | Feed human corrections back into the model. Disabling this stalls accuracy improvement. |
| `correction_propagation_enabled` | bool | `true` | — | Re-classify similar historical transactions when a category is corrected. |
| `correction_propagation_lookback_days` | int | `90` | `30 – 365` | How far back to re-classify on correction. |
| `split_transaction_enabled` | bool | `true` | — | Allow one transaction to be split across multiple categories. |
| `max_split_lines` | int | `10` | `2 – 50` | Maximum category splits per transaction. |
| `tax_code_validation` | bool | `true` | — | Validate assigned tax codes against chart of accounts mapping. |
| `strict_coa_mode` | bool | `true` | — | Reject categorisations to accounts not in the active chart of accounts. ⚠️ Disabling creates phantom accounts. |
| `bulk_categorise_batch_size` | int | `500` | `100 – 5000` | Transactions processed per batch run. |
| `recategorise_cooldown_hours` | int | `24` | `1 – 168` | Minimum time before auto-re-categorising a manually categorised transaction. Prevents overwriting human decisions. |
| `uncategorised_alert_threshold` | int | `50` | `10 – 500` | Alert if this many transactions remain uncategorised after a batch run. |
| `model_retrain_frequency_days` | int | `30` | `7 – 90` | How often the model retrains on accumulated corrections. |

**Note:** Confidence thresholds for this worker are engineering estimates, not sourced from a published benchmark. Flag for validation against your own model's precision/recall curve.

---

## 3. Receipt Processing

**Context:** IRS Publication 463 requires "adequate accounting" for expenses but does not specify a minimum dollar threshold for receipts — that is an organisational policy decision. The $25 threshold is the most widely cited industry standard across T&E platforms and auditor guidance.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `receipt_required_above` | int (minor units) | `2500` ($25) | `0 – 25000` | $25 is the most widely adopted receipt threshold across corporate T&E platforms and audit guidance. Some orgs use $20. [Emburse, Ramp, Rippling T&E guides] ⚠️ Setting above $75 creates IRS audit exposure. |
| `submission_deadline_days` | int | `30` | `7 – 60` | "Expense reports must be submitted within 30 days of trip completion." [Multiple T&E platform guides] |
| `max_receipt_age_days` | int | `90` | `30 – 365` | Receipt date must be within this many days of submission. |
| `ocr_confidence_min` | float (0–1) | `0.82` | `0.70 – 0.95` | Minimum OCR quality to auto-extract fields. Below this, require manual entry. |
| `duplicate_receipt_window_days` | int | `365` | `90 – 730` | Look-back for duplicate receipt detection (same merchant, amount, date). One full year recommended given annual resubmission patterns. |
| `currency_conversion_enabled` | bool | `true` | — | Auto-convert foreign currency using date-of-transaction rate. |
| `fx_rate_tolerance_pct` | float (0–1) | `0.03` | `0.01 – 0.10` | Accept claimed FX rate within 3% of mid-market rate on transaction date. |
| `auto_approve_below` | int (minor units) | `1000` ($10) | `0 – 5000` | Low-value receipts auto-approved if policy-compliant. |
| `image_min_quality_score` | float (0–1) | `0.60` | `0.40 – 0.90` | Reject blurry/illegible receipt images below this. |
| `merchant_category_block_list` | string[] | `["7995","5813"]` | — | Blocked MCCs (gambling 7995, bars/liquor 5813). |
| `personal_expense_detection` | bool | `true` | — | ML flag for likely personal expenses (grocery, pharmacy, etc.). |
| `vat_extraction_enabled` | bool | `true` | — | Extract VAT/GST line items for tax reclaim. |
| `missing_receipt_grace_period_days` | int | `7` | `1 – 30` | Days allowed to supply a missing receipt before the expense is rejected. |

**Sources:** IRS Publication 463; Emburse T&E policy guide; Ramp T&E policy guide; Rippling T&E guide.

---

## 4. Fraud Detection

**Context:** The European Banking Authority reported fraud represents 0.015% of total card payment value in Q1 2023 — illustrating severe class imbalance that drives false positive risk. Sift's 2024 *Fraud Industry Benchmarking Resource* reports false positive ratios of 6:1 to 9:1 at the 5% risk depth for best-in-class models. PSD2 (EU) mandates SCA alongside transaction monitoring for payments above €30. The Bank Secrecy Act (US) requires risk-based transaction monitoring.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `block_score_threshold` | float (0–1) | `0.90` | `0.80 – 0.99` | Hard-block above this. Setting below 0.85 drives false positive ratios above 9:1 at scale — destroying customer experience. [EBA fraud data; Sift FIBR 2024] ⚠️ |
| `review_score_threshold` | float (0–1) | `0.65` | `0.50 – 0.85` | Queue for analyst review between this and `block_score_threshold`. |
| `velocity_window_minutes` | int | `60` | `10 – 1440` | Rolling window for velocity checks. "Five rapid transactions in 10 minutes from the same account" is a canonical card-testing signal. [SEON, Chargebacks911] |
| `velocity_max_transactions` | int | `10` | `3 – 50` | Max transactions in the velocity window before flagging. |
| `velocity_max_amount` | int (minor units) | `500000` ($5,000) | — | Max cumulative spend in the velocity window. |
| `single_transaction_max` | int (minor units) | `1000000` ($10,000) | — | Hard per-transaction ceiling. ⚠️ |
| `new_merchant_risk_boost` | float | `0.15` | `0.05 – 0.30` | Additive score boost for merchants not seen in last 90 days. |
| `geo_velocity_max_kmph` | int | `800` | `200 – 1500` | Flag if consecutive transactions imply travel faster than this (card cloning signal). Typical long-haul flight speed ~900 km/h; 800 provides a margin. |
| `unusual_hours_start` | int (0–23) | `0` | — | Start of unusual-hours window (midnight). |
| `unusual_hours_end` | int (0–23) | `5` | — | End of unusual-hours window (5am). |
| `unusual_hours_risk_boost` | float | `0.10` | `0.05 – 0.25` | Score boost for transactions within the unusual-hours window. |
| `card_not_present_risk_boost` | float | `0.12` | `0.05 – 0.25` | Additional risk for CNP (online/phone) transactions. |
| `round_amount_risk_boost` | float | `0.08` | `0.0 – 0.20` | Round-number transaction amounts are a known fraud signal. |
| `high_risk_mcc_list` | string[] | `["6051","7995","6211"]` | — | MCCs that receive an automatic risk boost (money services 6051, gambling 7995, securities 6211). |
| `ip_reputation_check_enabled` | bool | `true` | — | Check CNP transaction IP against known bad-actor lists. [PSD2 SCA requirement for EU] |
| `device_fingerprint_enabled` | bool | `true` | — | Track device fingerprints; new device on high-value transaction adds to score. |
| `model_retrain_frequency_days` | int | `14` | `7 – 60` | Fraud patterns evolve fast. Monthly retraining is too slow — new attack patterns emerge in days. ⚠️ |
| `sca_required_above` | int (minor units) | `3000` (€30) | — | PSD2: Strong Customer Authentication required for online payments above €30. Set to jurisdiction-appropriate value. 📌 |

**Correction from v1:** `sca_required_above` added from PSD2 research. `velocity_max_transactions` validated against card-testing detection literature. False positive framing now grounded in EBA and Sift data.

**Sources:** EBA Payment Fraud Report 2024; Sift *Fraud Industry Benchmarking Resource* 2024; SEON velocity check explainer; Chargebacks911; Bank Secrecy Act (31 U.S.C. § 5318); PSD2 Article 97.

---

## 5. Collections

**Context:** CFPB *Regulation F* (effective November 30, 2021) codifies the FDCPA. Two hard regulatory limits apply: (1) contact hours are 8am–9pm in the debtor's local time; (2) collectors are *presumed* to violate the law if they call more than 7 times in 7 days about a single debt. These are not defaults — they are legal requirements.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `reminder_1_days_overdue` | int | `3` | `1 – 14` | Days past due before first gentle reminder. |
| `reminder_2_days_overdue` | int | `14` | `7 – 30` | Second reminder, firmer tone. |
| `reminder_3_days_overdue` | int | `30` | `21 – 60` | Third reminder with late fee notice. |
| `escalation_days_overdue` | int | `45` | `30 – 90` | Escalate to account manager / senior collections. |
| `final_notice_days_overdue` | int | `60` | `45 – 120` | Final notice before legal/agency referral. |
| `legal_referral_days_overdue` | int | `90` | `60 – 180` | Refer to legal or third-party agency. Industry data shows recovery rates drop sharply after 90 days. ⚠️ Many orgs wait 120–180 days. |
| `do_not_contact_start` | int (0–23) | `21` | — | **Legal requirement (FDCPA/Reg F):** No outbound contact after 9pm debtor's local time. 📌 |
| `do_not_contact_end` | int (0–23) | `8` | — | **Legal requirement (FDCPA/Reg F):** No outbound contact before 8am debtor's local time. 📌 |
| `max_calls_per_debt_per_week` | int | `7` | `1 – 7` | **CFPB Regulation F presumption:** >7 calls in 7 days about one debt is presumed to violate FDCPA. Hard ceiling at 7. 📌 ⚠️ Prior v1 had per-day limit of 2 — the actual rule is 7/week per debt. |
| `reminder_channel_priority` | string[] | `["email","sms","call"]` | — | Contact channel priority order. |
| `late_fee_enabled` | bool | `true` | — | Charge a late fee after `reminder_2_days_overdue`. Check jurisdiction caps before enabling. |
| `late_fee_fixed_amount` | int (minor units) | `4000` ($40) | `0 – 25000` | Fixed late fee per overdue invoice. |
| `late_fee_rate_annual_bps` | int | `1800` (18%) | `0 – 2400` | Annualised interest in bps. US consumer max typically 18–24%; UK statutory rate is 8% + Bank of England base rate (Late Payment of Commercial Debts Act 1998). |
| `late_fee_max_per_invoice_pct` | float (0–1) | `0.15` | `0.05 – 0.25` | Cap total late fees as percentage of invoice value. |
| `payment_plan_enabled` | bool | `true` | — | Allow customers to self-serve a payment plan. |
| `payment_plan_min_installments` | int | `2` | `2 – 24` | Minimum installments. |
| `payment_plan_max_months` | int | `12` | `3 – 36` | Maximum plan duration in months. |
| `dispute_hold_enabled` | bool | `true` | — | Pause collection on disputed invoices pending resolution. |
| `dispute_resolution_days` | int | `30` | `14 – 60` | SLA for resolving a dispute before resuming collections. |
| `minimum_balance_for_collections` | int (minor units) | `5000` ($50) | `0 – 50000` | Don't pursue balances below this — cost typically exceeds recovery. |

**Correction from v1:** `max_contact_attempts_per_day: 2` replaced with `max_calls_per_debt_per_week: 7` to correctly reflect CFPB Regulation F's actual rule structure. The per-day framing was wrong.

**Sources:** CFPB *Debt Collection Rule (Regulation F)*, effective November 30, 2021; CFPB FDCPA FAQ; Gryphon.ai FDCPA/TCPA guide; UK Late Payment of Commercial Debts (Interest) Act 1998.

---

## 6. Revenue Recognition

**Context:** ASC 606 (FASB) and IFRS 15 (IASB) are functionally aligned. Step 4 of the five-step model requires estimating variable consideration and applying the constraint: include variable amounts in the transaction price only to the extent it is *highly probable* that a significant revenue reversal will *not* occur. This is a qualitative legal standard — FASB does not assign a specific percentage. The 80% figure in v1 was an invention.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `recognition_standard` | enum | `"ASC_606"` | `ASC_606`, `IFRS_15` | Determines rule set. Nearly identical in practice; subtle differences exist in variable consideration treatment. |
| `default_recognition_method` | enum | `"over_time"` | `over_time`, `point_in_time` | Default for new contracts. SaaS and subscription businesses must use `over_time`. Defaulting to `point_in_time` for subscription revenue front-loads incorrectly. ⚠️ |
| `recognition_frequency` | enum | `"daily"` | `daily`, `monthly` | Daily is more accurate; monthly is more practical for reporting. |
| `variable_consideration_method` | enum | `"expected_value"` | `expected_value`, `most_likely_amount` | Use `expected_value` for large volumes of contracts with similar characteristics; `most_likely_amount` for binary outcomes (pass/fail bonus). [ASC 606-10-32-8; HubiFi] |
| `variable_consideration_constraint_enabled` | bool | `true` | — | Apply the ASC 606 constraint: only recognise variable amounts that are *highly probable* of not being reversed. This is a legal requirement under ASC 606-10-32-11, not a configuration choice. 📌 |
| `variable_consideration_review_frequency` | enum | `"each_reporting_date"` | `each_reporting_date`, `quarterly` | ASC 606-10-32-14 requires updating the constrained transaction price at each reporting date. `quarterly` is non-compliant for monthly reporters. 📌 |
| `ssp_estimation_method` | enum | `"adjusted_market"` | `adjusted_market`, `expected_cost_plus`, `residual` | Standalone selling price method. Use `residual` only when SSP is highly variable or uncertain — it is the method of last resort under ASC 606. |
| `contract_modification_handling` | enum | `"prospective"` | `prospective`, `cumulative_catch_up` | Prospective is simpler and less error-prone. Cumulative catch-up is required when a modification is treated as a continuation of the existing contract. |
| `material_right_tracking_enabled` | bool | `true` | — | Renewal options or discounts that are a material right must be treated as a separate performance obligation under ASC 606-10-55-42. |
| `milestone_completion_threshold_pct` | float (0–1) | `1.00` | `0.80 – 1.00` | Percentage of milestone completion required before recognising associated revenue. 100% is safest for output-method recognition. |
| `auto_close_completed_obligations` | bool | `true` | — | Auto-close and recognise remaining revenue when an obligation is marked 100% complete. |
| `period_lock_enforcement` | bool | `true` | — | Block recognition entries in locked accounting periods. ⚠️ Disabling allows retroactive manipulation. |
| `deferred_revenue_account_id` | string | — | — | Must be configured. No default possible — maps to your chart of accounts. |
| `revenue_account_id` | string | — | — | Must be configured. No default possible. |

**Correction from v1:** Removed the `variable_consideration_constraint_pct: 0.80` parameter entirely — FASB does not specify a percentage. The standard uses the qualitative "highly probable" threshold. Replaced with `variable_consideration_method` and `variable_consideration_constraint_enabled`.

**Sources:** FASB ASC 606-10-32-8, -11, -14; BillingPlatform ASC 606 variable consideration guide; RevenueHub variable consideration constraint article; HubiFi ASC 606 guide.

---

## 7. Credit Underwriting

**Context:** The CFPB's 2020 General QM Final Rule replaced the hard 43% DTI ceiling with a price-based approach (APR vs. APOR spread). However, the 43% DTI figure remains widely used as an internal underwriting reference by lenders and is still cited in industry standards — it just no longer determines QM safe harbour status. Fannie Mae eliminated its 620 minimum FICO for DU-processed loans in November 2025, but most private lenders maintain 620 as a de facto floor.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `min_credit_score` | int | `620` | `500 – 750` | 620 is the conventional industry floor for prime/near-prime. Fannie Mae dropped its DU minimum in Nov 2025; many private lenders still enforce 620. [CFPB QM rule; Upstart; SoFi] ⚠️ |
| `auto_approve_score_min` | int | `720` | `680 – 800` | Scores above this with all other criteria met can be auto-approved. |
| `manual_review_score_min` | int | `620` | — | Scores in `[min_credit_score, auto_approve_score_min)` go to manual underwriter review. |
| `max_dti_ratio` | float (0–1) | `0.43` | `0.30 – 0.55` | 43% was the QM hard cap; CFPB moved to a price-based approach in 2020 but lenders still use 43% as an internal guideline. Conservative underwriting targets 36%. [CFPB QM Final Rule 2020] ⚠️ |
| `max_ltv_ratio` | float (0–1) | `0.80` | `0.60 – 0.97` | Above 80% LTV typically requires PMI or equivalent for mortgages. |
| `min_employment_months` | int | `6` | `3 – 24` | Minimum continuous employment history. |
| `min_annual_income` | int (minor units) | `2000000` ($20,000) | — | Minimum annual income to qualify. |
| `max_loan_amount` | int (minor units) | `50000000` ($500,000) | — | Hard cap per single application. |
| `min_loan_amount` | int (minor units) | `100000` ($1,000) | — | Don't underwrite below this — unit economics typically don't support it. |
| `max_term_months` | int | `84` | `12 – 360` | Max loan term (7 years for personal; 30 years for mortgage). |
| `max_open_derogatory_marks` | int | `0` | `0 – 2` | Hard decline if applicant has more than this many open derogatory marks. |
| `bankruptcy_lookback_years` | int | `7` | `3 – 10` | Hard decline if bankruptcy discharged within this many years. |
| `fraud_check_enabled` | bool | `true` | — | Run identity and synthetic-identity fraud checks before bureau pull. Never disable. ⚠️ |
| `bureau_providers` | string[] | `["equifax","experian","transunion"]` | — | Tri-merge uses middle score. Single-bureau pull increases adverse selection risk. |
| `income_verification_required_above` | int (minor units) | `5000000` ($50,000) | — | Documented income required above this amount; not stated income. |
| `adverse_action_notice_auto` | bool | `true` | — | Auto-generate ECOA adverse action notices on declines. Legal requirement under 15 U.S.C. § 1691(d). 📌 |

**Correction from v1:** DTI context updated to reflect that the CFPB's 43% hard cap was replaced by a price-based approach in 2020, while noting that 43% remains a practical industry benchmark. Fannie Mae's November 2025 score floor change noted.

**Sources:** CFPB *General QM Loan Definition Final Rule* 2020; CFPB QM summary; Upstart 620 credit score guide; FDIC *Small Business Lending Survey 2024*; U.S. News / Fannie Mae FICO change (Nov 2025); ECOA 15 U.S.C. § 1691(d).

---

## 8. Compliance (AML / KYC / Sanctions / GDPR)

**Context:** This is the most heavily regulated worker. Key hard rules: FinCEN CTR threshold is $10,000 (set in 1970, never inflation-adjusted — GAO flagged this in 2025). Structuring is a federal crime under 31 U.S.C. § 5324 regardless of whether the underlying funds are legitimate. OFAC expects real-time or near-real-time sanctions screening — a bank was penalised for a two-week gap after an SDN list update. FATF KYC refresh: annually for high-risk, 3–5 years for low-risk customers.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `aml_monitoring_enabled` | bool | `true` | — | Master switch. Never disable in production. 📌 |
| `ctr_threshold` | int (minor units) | `1000000` ($10,000) | — | US CTR reporting threshold per 31 U.S.C. § 5313. Set to jurisdiction-appropriate value. EU: €10,000 for occasional transactions (FATF Rec 10). 📌 |
| `structuring_window_hours` | int | `24` | `12 – 168` | Rolling window for detecting structuring patterns. |
| `structuring_transaction_count_min` | int | `3` | `2 – 10` | Minimum transactions in the window to trigger a structuring alert. |
| `structuring_cumulative_threshold` | int (minor units) | `900000` ($9,000) | — | Flag cumulative transactions in window exceeding this. Set ~10% below the CTR threshold. ⚠️ Setting this equal to or above the CTR threshold completely defeats structuring detection. |
| `sar_auto_file_enabled` | bool | `false` | — | Do not auto-file SARs. Regulators in most jurisdictions expect a human compliance officer to review and sign off. Auto-filing is considered bad practice. ⚠️ |
| `sar_review_queue_enabled` | bool | `true` | — | High-risk transactions route to SAR review queue for compliance officer decision. |
| `sanctions_list_providers` | string[] | `["OFAC","UN","EU"]` | — | OFAC mandatory for US entities; UN and EU lists for global coverage. 📌 |
| `sanctions_refresh_frequency` | enum | `"realtime"` | `realtime`, `daily`, `weekly` | OFAC expects real-time or near-real-time refresh. A bank was penalised for a ~2-week gap after an SDN list update. Daily is the minimum acceptable. 📌 ⚠️ |
| `pep_screening_enabled` | bool | `true` | — | Screen counterparties against Politically Exposed Persons lists. Required for most regulated entities. 📌 |
| `adverse_media_screening_enabled` | bool | `true` | — | Screen for negative news during onboarding and periodic review. |
| `kyc_refresh_standard_days` | int | `1825` (5 years) | `1095 – 1825` | Periodic KYC refresh for standard-risk customers. FATF: 3–5 years. [EY KYC refresh guide; FATF Rec 10] |
| `kyc_refresh_high_risk_days` | int | `365` (1 year) | `90 – 365` | Annual refresh for high-risk customers. FATF Recommendation 10 requires more frequent monitoring for high-risk profiles. [AML Network; EY KYC guide] |
| `high_risk_jurisdiction_list_enabled` | bool | `true` | — | Flag transactions involving FATF grey/black-listed jurisdictions. |
| `gdpr_data_retention_days` | int | `2555` (7 years) | `365 – 3650` | Retain financial records for 7 years (common AML/accounting requirement). Personal data beyond this scope must be deleted under GDPR Article 17. |
| `gdpr_erasure_aml_hold_check` | bool | `true` | — | Before any erasure, verify no AML retention obligation or legal hold applies. |
| `transaction_monitoring_lookback_days` | int | `365` | `90 – 730` | Historical window for behavioural baseline. |
| `fatf_occasional_transaction_threshold` | int (minor units) | `1500000` ($15,000) | — | FATF Recommendation 10: standard CDD required for occasional transactions above $15,000. 📌 |

**Correction from v1:** `sanctions_refresh_hours: 24` updated to `sanctions_refresh_frequency: "realtime"` based on OFAC enforcement precedent. KYC refresh intervals now cited to FATF/EY. `sar_auto_file_enabled` explicitly set to `false` with explanation. $15,000 FATF occasional transaction threshold added.

**Sources:** FinCEN CTR FAQ; FinCEN CTR Pamphlet; 31 U.S.C. § 5313 (CTR) and § 5324 (structuring); GAO-25-106500 (2025); FATF Recommendation 10; Hunton Andrews Kurth — *OFAC to Banks: Implement Continuous Sanctions Monitoring*; EY *KYC Refresh: Building an Effective Risk-Based Program*; AML Network KYC refresh guidance; Sanctions.io AML best practices.

---

## 9. Reconciliation

**Context:** Published best practice (Washington State Auditor's Office, Numeric, HighRadius) converges on: 3–5 business day date tolerance for timing differences; absolute + percentage combined tolerance for amount matching; daily reconciliation for high-volume operations; investigate every unmatched item — don't let items age.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `auto_match_confidence_min` | float (0–1) | `0.95` | `0.85 – 1.00` | Minimum confidence for automatic matching. ⚠️ Lowering this to reduce queue size creates incorrect matches that compound at month-end. |
| `amount_tolerance_minor_units` | int | `150` ($1.50) | `0 – 1000` | Accept matches with an amount difference up to this value. "$1.50 absolute tolerance" cited in Numeric reconciliation guide. |
| `amount_tolerance_pct` | float (0–1) | `0.0003` (0.03%) | `0 – 0.01` | Percentage-based tolerance for large transactions. "0.03%" cited in Numeric guide. Combine with absolute using OR logic. |
| `date_tolerance_days` | int | `5` | `0 – 14` | Match transactions within this many business days (handles bank processing lag). "3 to 5 business days" is the documented range. ⚠️ Setting to 0 causes mass false unmatched items. |
| `partial_match_enabled` | bool | `true` | — | One bank line can match multiple ledger entries (common for batch payments). |
| `partial_match_max_lines` | int | `20` | `2 – 100` | Maximum ledger lines per bank transaction in a partial match. |
| `reconciliation_frequency` | enum | `"daily"` | `real_time`, `daily`, `weekly` | "High-volume operations should consider daily reviews." [HighRadius; Emagia] Weekly is acceptable only for very low-volume books. |
| `unmatched_alert_days` | int | `5` | `1 – 30` | Flag items unmatched for more than this many business days. ⚠️ Setting to 30+ lets items age until they become hard to resolve. |
| `forex_tolerance_pct` | float (0–1) | `0.02` | `0 – 0.05` | For multi-currency accounts, allow 2% variance from the recorded FX rate (covers rate movements between booking and settlement). |
| `intercompany_auto_eliminate` | bool | `false` | — | Keep false until thoroughly tested. Auto-elimination errors in consolidation are hard to trace. |
| `stale_open_item_days` | int | `90` | `30 – 365` | Flag open reconciling items older than this for write-off review. |
| `suspense_account_id` | string | — | — | Must be configured. Unmatched items park here temporarily. |
| `period_lock_respect` | bool | `true` | — | Do not create adjustment entries in locked periods. |
| `segregation_of_duties_enforced` | bool | `true` | — | The reconciliation function must be segregated from record-keeping. [Washington State Auditor best practices] 📌 |

**Correction from v1:** Amount tolerance updated from `5 cents` to `$1.50` (Numeric's cited figure). Date tolerance confirmed as 3–5 days. `segregation_of_duties_enforced` parameter added based on auditor guidance.

**Sources:** Washington State Auditor's Office *Best Practices for Bank Reconciliations*; Numeric *Transaction Reconciliation Guide*; HighRadius bank reconciliation guide; Emagia reconciliation frequency guide; Brex accounting reconciliation guide.

---

## 10. Expense Control

**Context:** IRS Publication 463 governs adequate accounting for business expenses but does not set a specific receipt threshold — that's an organisational decision. $25 is the practical industry standard. The GBTA and major T&E platforms (Emburse, Ramp, Rippling) consistently cite $25 as the norm. Cash advance on corporate cards is almost never a legitimate expense — it's a primary fraud vector.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `per_transaction_limit` | int (minor units) | `50000` ($500) | `0 – 1000000` | Hard block on any single expense transaction above this. No ceiling = no protection. ⚠️ |
| `daily_spend_limit` | int (minor units) | `200000` ($2,000) | — | Cumulative daily spend cap per employee/card. |
| `monthly_spend_limit` | int (minor units) | `500000` ($5,000) | — | Cumulative monthly spend cap per employee/card. |
| `receipt_required_above` | int (minor units) | `2500` ($25) | `0 – 25000` | $25 is the widely adopted industry standard. IRS Pub 463 has no fixed minimum but requires adequate documentation. [Emburse, Ramp, Rippling] ⚠️ |
| `pre_approval_required_above` | int (minor units) | `100000` ($1,000) | — | Expenses above this require prior manager approval. |
| `blocked_mcc_list` | string[] | `["7995","5813","7011"]` | — | Blocked MCCs: gambling (7995), bars/liquor (5813), hotels unless travel-approved (7011). |
| `blocked_mcc_allow_override` | bool | `false` | — | Whether blocked MCCs can be overridden with manager approval. |
| `weekend_spend_enabled` | bool | `true` | — | Disable only for office-only programmes where weekend spend is never legitimate. |
| `international_spend_enabled` | bool | `true` | — | Disable for domestic-only card programmes. |
| `cash_advance_enabled` | bool | `false` | — | Block cash advances. Rarely legitimate on corporate cards; primary fraud vector. ⚠️ |
| `atm_withdrawal_enabled` | bool | `false` | — | Block ATM withdrawals. Route petty cash through a separate process. |
| `meals_per_diem_limit` | int (minor units) | `10000` ($100) | — | Daily meals cap per employee when travelling. Adjust to local cost of living. |
| `hotel_daily_rate_limit` | int (minor units) | `35000` ($350) | — | Maximum accepted hotel rate per night before flagging. |
| `entertainment_monthly_limit` | int (minor units) | `25000` ($250) | — | Monthly cap on client entertainment per employee. |
| `policy_violation_warning_count` | int | `3` | `1 – 10` | Violations before escalating to manager notification. |
| `policy_violation_suspend_count` | int | `5` | `3 – 20` | Violations before card is temporarily suspended pending review. |

**Sources:** IRS Publication 463; Emburse T&E policy guide; Ramp T&E policy guide; Rippling T&E guide; GBTA Expense Management hub.

---

## 11. Treasury

**Context:** The 13-week rolling cash flow forecast is the CFO gold standard — it "balances detail with actionability and allows teams to spot potential shortfalls 8–10 weeks early" (PKF O'Connor Davies). Cash alert thresholds should be calibrated to actual burn rate: best practice is to alert when cash falls below 45–60 days of expenses (Sagelight CFO guide), not a fixed dollar amount. FDIC insures up to $250,000 per depositor per institution; the SVB collapse (2023) demonstrated the catastrophic risk of uninsured deposit concentration — SVB had 88% uninsured deposits at failure.

| Parameter | Type | Recommended Default | Typical Range | Notes |
|---|---|---|---|---|
| `minimum_operating_balance_alert_days` | int | `45` | `30 – 90` | Alert when projected cash covers fewer than this many days of expenses. "45–60 days of expenses" is the cited best practice threshold. [Sagelight CFO guide] ⚠️ A fixed dollar amount is wrong — calibrate to burn rate. |
| `critical_balance_alert_days` | int | `14` | `7 – 30` | Critical CFO alert when projected cash covers fewer than this many days. |
| `runway_alert_days` | int | `90` | `30 – 365` | Alert when total runway (cash / monthly burn) drops below this. Gives meaningful response time for fundraising or cost action. |
| `runway_critical_days` | int | `30` | `14 – 60` | Critical alert when runway drops below this. |
| `forecast_horizon_days` | int | `91` | `30 – 365` | 13-week rolling forecast = 91 days. "The 13-week cash flow forecast is the CFO's gold standard." [PKF O'Connor Davies] |
| `forecast_update_frequency` | enum | `"weekly"` | `daily`, `weekly`, `monthly` | 13-week model is "updated weekly" per PKF. Daily is better for high-volatility businesses. |
| `forecast_method` | enum | `"hybrid"` | `simple_moving_avg`, `weighted_moving_avg`, `ml_forecast`, `hybrid` | Hybrid (statistical + ML) outperforms simple averages. |
| `cash_sweep_enabled` | bool | `false` | — | Only enable once thresholds are well calibrated and tested. Auto-sweeping with miscalibrated thresholds strands operating cash. |
| `cash_sweep_threshold` | int (minor units) | `50000000` ($500,000) | — | Sweep excess above this into a money market account. |
| `cash_sweep_retain_minimum` | int (minor units) | `10000000` ($100,000) | — | Always retain at least this after any sweep. |
| `investment_policy_min_rating` | string | `"A"` | `AAA`, `AA`, `A`, `BBB` | Minimum credit rating of permitted short-term investments. |
| `bank_counterparty_limit` | int (minor units) | `25000000` ($250,000) | — | Maximum uninsured cash at any single bank. FDIC insures up to $250,000 per depositor per institution. SVB: 88% of deposits were uninsured at failure. 📌 ⚠️ |
| `bank_counterparty_count_min` | int | `2` | `1 – 10` | Minimum number of banking relationships. Single-bank concentration is an SVB-class risk. |
| `investment_max_single_counterparty_pct` | float (0–1) | `0.25` | `0.10 – 0.50` | Cap any single institution as percentage of total investable cash. |
| `fx_exposure_alert_pct` | float (0–1) | `0.20` | `0.05 – 0.50` | Alert when unhedged FX exposure exceeds this percentage of total cash. |
| `ar_aging_visibility_enabled` | bool | `true` | — | Include AR aging in forecast (expected inflows from receivables). AR past 60 days >20% is a cash risk signal. |
| `payroll_reserve_days` | int | `5` | `3 – 14` | Days before payroll to ring-fence sufficient cash. ⚠️ Setting to 1 leaves zero buffer for bank processing delays. |
| `daily_reconciliation_enabled` | bool | `true` | — | Reconcile treasury positions against bank statements daily. |

**Correction from v1:** `minimum_operating_balance_alert` changed from a fixed dollar amount (`$50,000`) to a burn-rate-relative days parameter (`minimum_operating_balance_alert_days: 45`). This reflects actual CFO best practice. `bank_counterparty_limit` reduced to the FDIC insurance ceiling ($250,000) with SVB context. `forecast_horizon_days` updated to 91 (13 weeks) with source. `forecast_update_frequency` changed to weekly to match the 13-week model cadence.

**Sources:** PKF O'Connor Davies *A CFO's Lifeline: Mastering the 13-Week Cash Flow Forecast*; Sagelight *Cash Flow Management: The CFO's Guide*; FDIC *Your Insured Deposits*; Brookings Institution — *Should the US raise the $250,000 ceiling on deposit insurance?*; Congress.gov *Deposit Insurance and the Failures of SVB and Signature Bank*; AFP 2025 Treasury Benchmarking Survey.

---

## Cross-Worker Consistency Checklist

These settings appear in multiple workers and must be kept consistent:

| Setting | Workers | Risk of inconsistency |
|---|---|---|
| `receipt_required_above` | Receipt Processing, Expense Control | Different thresholds create a policy gap users will exploit |
| `period_lock_enforcement` | Revenue Recognition, Reconciliation | One worker can post into locked periods if the other doesn't enforce |
| `duplicate_window_days` | Invoice Processing, Receipt Processing | Different windows allow resubmission bypass |
| `blocked_mcc_list` | Expense Control, Receipt Processing | If Receipt Processing approves what Expense Control blocks, policy is undermined |
| `model_retrain_frequency_days` | Fraud Detection, AI Accountant | Stale models in either worker degrade the other's upstream data |
| `do_not_contact_start/end` | Collections | Must reflect debtor's *local* time zone, not system time zone 📌 |

---

## What Changed From v1 (Key Corrections)

| Worker | Parameter | v1 (estimate) | v2 (sourced) | Source |
|---|---|---|---|---|
| Collections | `max_contact_attempts_per_day: 2` | Replaced | `max_calls_per_debt_per_week: 7` | CFPB Regulation F |
| Compliance | `sanctions_refresh_hours: 24` | Replaced | `sanctions_refresh_frequency: "realtime"` | OFAC enforcement action |
| Compliance | `sar_auto_file_score_threshold` | Removed | `sar_auto_file_enabled: false` | Regulatory expectation |
| Compliance | `kyc_refresh_frequency_days: 365` | Split | Standard: 5yr, High-risk: 1yr | FATF Recommendation 10 |
| Compliance | `fatf_occasional_transaction_threshold` | Missing | Added: $15,000 | FATF Recommendation 10 |
| Revenue Recognition | `variable_consideration_constraint_pct: 0.80` | Removed | Qualitative standard; no %; replaced with method enum | FASB ASC 606-10-32-11 |
| Credit Underwriting | `max_dti_ratio: 0.43` | Now correctly contextualised | Hard cap removed by CFPB 2020; still industry reference | CFPB QM Final Rule 2020 |
| Treasury | `minimum_operating_balance_alert: $50,000` | Replaced | `minimum_operating_balance_alert_days: 45` | Sagelight CFO guide |
| Treasury | `bank_counterparty_limit: $5,000,000` | Replaced | `$250,000` (FDIC ceiling) | FDIC; SVB post-mortem |
| Treasury | `forecast_horizon_days: 90` | Updated | 91 days (13 weeks) | PKF O'Connor Davies |
| Invoice | `po_tolerance_pct: 0.05` | Tightened | `0.03` | Klippa AP guide |
| Reconciliation | `amount_tolerance_minor_units: 5` | Updated | `150` ($1.50) | Numeric reconciliation guide |

---

## Full Bibliography

- [FinCEN CTR FAQ](https://www.fincen.gov/resources/frequently-asked-questions-regarding-fincen-currency-transaction-report-ctr)
- [FinCEN CTR Pamphlet](https://www.fincen.gov/system/files/shared/CTRPamphlet.pdf)
- [GAO-25-106500: Currency Transaction Reports](https://www.gao.gov/products/gao-25-106500)
- [CFPB Debt Collection Rule (Regulation F)](https://www.consumerfinance.gov/rules-policy/final-rules/debt-collection-practices-regulation-f/)
- [CFPB Debt Collection Rule FAQs](https://www.consumerfinance.gov/compliance/compliance-resources/other-applicable-requirements/debt-collection/debt-collection-rule-faqs/)
- [CFPB FDCPA Overview](https://www.consumerfinance.gov/compliance/compliance-resources/other-applicable-requirements/debt-collection/)
- [Gryphon.ai Collections Contact Compliance Guide](https://gryphon.ai/what-is-collections-contact-compliance-for-debt-collection-communications/)
- [CFPB General QM Final Rule](https://www.consumerfinance.gov/rules-policy/final-rules/qualified-mortgage-definition-under-truth-lending-act-regulation-z-general-qm-loan-definition/)
- [HousingWire: CFPB eliminates DTI from QM standards](https://www.housingwire.com/articles/cfpb-to-eliminate-dti-requirement-from-qualified-mortgage/)
- [Fannie Mae drops minimum FICO score](https://money.usnews.com/loans/mortgages/articles/fannie-mae-drops-minimum-fico-score-requirement)
- [Upstart: 620 Credit Score](https://www.upstart.com/credit-score/620-credit-score)
- [FDIC Small Business Lending Survey 2024](https://www.fdic.gov/publications/small-business-lending-survey-2024-section-3-loan-underwriting-and-approval)
- [FATF Recommendations Overview — Flagright](https://www.flagright.com/post/the-role-of-fatf-recommendations-in-shaping-global-aml-strategies)
- [Sumsub AML Transaction Monitoring 2026](https://sumsub.com/blog/transaction-monitoring/)
- [Sanctions.io AML Best Practices](https://www.sanctions.io/blog/transaction-monitoring-aml-compliance-best-practices)
- [Hunton Andrews Kurth: OFAC Continuous Monitoring](https://www.hunton.com/insights/legal/ofac-to-banks-implement-continuous-sanctions-monitoring)
- [EY: KYC Refresh Best Practices](https://www.ey.com/en_us/insights/financial-services/kyc-refresh-effective-risk-based-program)
- [AML Network: KYC FATF Guidelines](https://amlnetwork.org/aml-glossary/kyc-fatf-guidelines/)
- [BillingPlatform: Variable Consideration ASC 606](https://billingplatform.com/blog/variable-consideration-asc-606)
- [RevenueHub: Variable Consideration Constraint](https://www.revenuehub.org/article/variable-consideration-constraint)
- [HubiFi: Variable Consideration ASC 606](https://www.hubifi.com/blog/variable-consideration-under-asc-606)
- [Washington State Auditor: Bank Reconciliation Best Practices](https://sao.wa.gov/sites/default/files/2023-05/Best-Practices-for-Bank-Reconciliations.pdf)
- [Numeric: Transaction Reconciliation Guide](https://www.numeric.io/blog/transaction-reconciliation-guide)
- [HighRadius: Bank Reconciliation Guide](https://www.highradius.com/resources/Blog/how-to-do-bank-reconciliation/)
- [Ramp: 3-Way Match in AP](https://ramp.com/blog/accounts-payable/3-way-match)
- [Klippa: 3-Way Invoice Matching](https://www.klippa.com/en/blog/information/three-way-matching/)
- [ACFE: Fraudify Wrapped 2024](https://www.acfe.com/acfe-insights-blog/blog-detail?s=fraudify-wrapped-2024)
- [Emburse: ACFE 2024 Report Key Findings](https://www.emburse.com/blog/finance-fraud-and-frustration-key-findings-from-the-acfe-2024-report)
- [EBA Payment Fraud Statistics (cited via Sift)](https://sift.com/blog/new-2024-fraud-industry-benchmarking-resource-data/)
- [Sift FIBR 2024](https://sift.com/blog/new-2024-fraud-industry-benchmarking-resource-data/)
- [SEON: Velocity Checks](https://seon.io/resources/dictionary/velocity-check/)
- [Chargebacks911: Velocity Checks](https://chargebacks911.com/velocity-checks/)
- [PKF O'Connor Davies: 13-Week Cash Flow Forecast](https://www.pkfod.com/insights/a-cfos-lifeline-mastering-the-13-week-cash-flow-forecast/)
- [Sagelight: CFO Cash Flow Management Guide](https://sagelight.ai/blog/cash-flow-management-the-cfos-guide/)
- [FDIC: Your Insured Deposits](https://www.fdic.gov/resources/deposit-insurance/brochures/insured-deposits)
- [Brookings: Deposit Insurance Debate](https://www.brookings.edu/articles/a-debate-should-u-s-raise-the-250000-ceiling-on-deposit-insurance/)
- [Congress.gov: SVB Deposit Insurance](https://www.congress.gov/crs-product/IF12361)
- [AFP 2025 Treasury Benchmarking Survey](https://www.financialprofessionals.org/training-resources/resources/survey-research-economic-data/Details/treasury-benchmarking)
- [IRS Publication 463](https://www.irs.gov/publications/p463)
- [Emburse T&E Policy Guide](https://www.emburse.com/resources/travel-and-expense-policy-steps-template-best-practices)
- [Ramp T&E Policy Guide](https://ramp.com/blog/how-to-create-a-travel-and-expense-policy)