"""
Unit tests for spend_control policy / limit logic.

Covers the pure decision helpers (hard rules, duplicate detection, early-payment
discount parsing, supplier grouping, policy parsing) plus a guard that the job
runner finalizes through complete_execution and returns its decision.
No DB or Claude calls — the pure helpers take plain records; the runner test mocks
_execute_expense_control and complete_execution.
"""
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.spend_control import (
    _apply_hard_rules,
    _BillRecord,
    _detect_duplicates,
    _detect_early_payment_discounts,
    _ExpenseRecord,
    _ExpenseToolPolicy,
    _group_by_supplier,
    _parse_ap_policy,
    _parse_expense_policy,
)


def _expense(**overrides) -> _ExpenseRecord:
    defaults = dict(
        id="exp1",
        tenant_id="t1",
        amount_cents=5_000,
        category="Software",
        account_code="400",
        approved=True,
        expense_date=datetime.now(UTC),
        contact_name="Acme",
    )
    defaults.update(overrides)
    return _ExpenseRecord(**defaults)


def _bill(**overrides) -> _BillRecord:
    defaults = dict(
        id="bill1",
        vendor_id="v1",
        contact_name="Acme",
        total_cents=10_000,
        outstanding_cents=10_000,
        issue_date=date.today(),
        due_date=date.today(),
        status="open",
    )
    defaults.update(overrides)
    return _BillRecord(**defaults)


_VALID_CODES = {"400", "500"}
_POLICY = _ExpenseToolPolicy()  # single 100_000 / approval 50_000 / auto 10_000


class TestApplyHardRules:
    def test_over_single_limit_blocks(self):
        flags, action = _apply_hard_rules(_expense(amount_cents=150_000), _VALID_CODES, _POLICY)
        assert action == "block"
        assert flags

    def test_unapproved_over_approval_threshold_flags(self):
        # 55_000: unapproved, over approval_required (50_000), not a round number, under single limit
        flags, action = _apply_hard_rules(
            _expense(amount_cents=55_000, approved=False), _VALID_CODES, _POLICY
        )
        assert action == "flag"
        assert any("unapproved" in f.lower() for f in flags)

    def test_account_code_not_in_chart_flags(self):
        flags, action = _apply_hard_rules(
            _expense(amount_cents=5_000, account_code="9999"), _VALID_CODES, _POLICY
        )
        assert action == "flag"
        assert any("miscategoris" in f.lower() for f in flags)

    def test_suspicious_round_number_flags(self):
        # 70_000: approved, valid path, but a round multiple of 100 above 500
        flags, action = _apply_hard_rules(
            _expense(amount_cents=70_000, account_code=None), _VALID_CODES, _POLICY
        )
        assert action == "flag"
        assert any("round-number" in f.lower() for f in flags)

    def test_clean_expense_no_action(self):
        flags, action = _apply_hard_rules(_expense(), _VALID_CODES, _POLICY)
        assert action is None
        assert flags == []

    def test_block_outranks_flag(self):
        # Over single limit AND unapproved — worst action must win.
        flags, action = _apply_hard_rules(
            _expense(amount_cents=200_000, approved=False), _VALID_CODES, _POLICY
        )
        assert action == "block"

    def test_empty_chart_skips_account_check(self):
        # No known codes → cannot judge miscategorisation, must not flag on that basis.
        flags, action = _apply_hard_rules(
            _expense(amount_cents=5_000, account_code="ANYTHING"), set(), _POLICY
        )
        assert action is None


class TestPolicyParsing:
    def test_flat_config_parsed(self):
        p = _parse_expense_policy({"single_expense_limit_cents": 200_000})
        assert p.single_expense_limit_cents == 200_000

    def test_nested_policy_key_parsed(self):
        p = _parse_expense_policy({"policy": {"auto_approve_limit_cents": 2_500}})
        assert p.auto_approve_limit_cents == 2_500

    def test_unknown_keys_ignored(self):
        p = _parse_expense_policy({"single_expense_limit_cents": 90_000, "junk": "x"})
        assert p.single_expense_limit_cents == 90_000

    def test_ap_policy_defaults_and_overrides(self):
        assert _parse_ap_policy({}).auto_pay_limit_cents == 50_000
        assert _parse_ap_policy({"auto_pay_limit_cents": 12_345}).auto_pay_limit_cents == 12_345


class TestDuplicateDetection:
    def test_same_contact_and_total_within_window_flagged(self):
        b1 = _bill(id="a", issue_date=date(2026, 1, 1))
        b2 = _bill(id="b", issue_date=date(2026, 1, 10))
        _detect_duplicates([b1, b2], window_days=30)
        assert b1.is_duplicate and b2.is_duplicate

    def test_different_totals_not_flagged(self):
        b1 = _bill(id="a", total_cents=10_000)
        b2 = _bill(id="b", total_cents=20_000)
        _detect_duplicates([b1, b2], window_days=30)
        assert not b1.is_duplicate and not b2.is_duplicate

    def test_outside_window_not_flagged(self):
        b1 = _bill(id="a", issue_date=date(2026, 1, 1))
        b2 = _bill(id="b", issue_date=date(2026, 3, 1))
        _detect_duplicates([b1, b2], window_days=30)
        assert not b1.is_duplicate and not b2.is_duplicate


class TestEarlyPaymentDiscount:
    def test_discount_available_within_window(self):
        b = _bill(payment_terms="2/10 net 30", issue_date=date.today(), outstanding_cents=100_000)
        _detect_early_payment_discounts([b])
        assert b.early_payment_discount_available
        assert b.early_payment_discount_pct == 2.0
        assert b.early_payment_discount_cents == 2_000  # integer minor units, no float

    def test_discount_expired_outside_window(self):
        b = _bill(payment_terms="2/10 net 30", issue_date=date.today() - timedelta(days=20))
        _detect_early_payment_discounts([b])
        assert not b.early_payment_discount_available

    def test_no_terms_no_discount(self):
        b = _bill(payment_terms=None)
        _detect_early_payment_discounts([b])
        assert not b.early_payment_discount_available


class TestSupplierGrouping:
    def test_groups_only_multi_bill_vendors(self):
        bills = [
            _bill(id="a", vendor_id="v1"),
            _bill(id="b", vendor_id="v1"),
            _bill(id="c", vendor_id="v2"),
        ]
        groups = _group_by_supplier(bills)
        assert len(groups) == 1
        g = groups[0]
        assert g["supplier_id"] == "v1"
        assert set(g["bill_ids"]) == {"a", "b"}
        assert g["supplier_total_minor"] == 20_000


class TestJobRunnerFinalization:
    """The runner must finalize via complete_execution and return the decision it
    produces (the tool's own policy decision)."""

    @pytest.mark.asyncio
    async def test_expense_job_finalizes_via_complete_execution(self):
        tool_result = {
            "decision": "approval_required",
            "confidence": 0.4,
            "reasoning": "{}",
            "actions_taken": [],
            "output_data": {},
        }
        db = MagicMock()
        complete = AsyncMock(return_value="approval_required")  # complete_execution's final decision

        with (
            patch("app.tools.spend_control.get_db", return_value=db),
            patch("app.tools.spend_control._execute_expense_control",
                  AsyncMock(return_value=tool_result)),
            patch("app.tools.spend_control.complete_execution", complete),
        ):
            from app.tools.spend_control import run_expense_control_job
            result = await run_expense_control_job(
                {}, execution_id="e1", tenant_id="t1", tool_id="w1",
            )

        complete.assert_awaited_once()
        kwargs = complete.await_args.kwargs
        assert kwargs["decision"] == "approval_required"
        assert kwargs["tenant_id"] == "t1"
        assert result["decision"] == "approval_required"

    @pytest.mark.asyncio
    async def test_expense_job_failure_marks_execution_failed(self):
        db = MagicMock()
        db.execution.update = AsyncMock(return_value=None)

        with (
            patch("app.tools.spend_control.get_db", return_value=db),
            patch("app.tools.spend_control._execute_expense_control",
                  AsyncMock(side_effect=RuntimeError("boom"))),
            patch("app.tools.spend_control.push_to_dlq", AsyncMock()),
        ):
            from app.tools.spend_control import run_expense_control_job
            with pytest.raises(RuntimeError, match="boom"):
                await run_expense_control_job(
                    {}, execution_id="e1", tenant_id="t1", tool_id="w1",
                )

        db.execution.update.assert_awaited()
        assert db.execution.update.await_args.kwargs["data"]["status"] == "failed"


class TestPersistControlStatus:
    """The writeback that lets Payment Runs respect Spend Control's verdict."""

    def _model(self):
        m = MagicMock()
        m.update_many = AsyncMock()
        return m

    @pytest.mark.asyncio
    async def test_approved_batched_into_single_update(self):
        from app.tools.spend_control import _persist_control_status
        model = self._model()
        await _persist_control_status(model, "t1", [
            ("a", "approved", "ok"), ("b", "approved", "ok"), ("c", "approved", "ok"),
        ])
        # one batched update_many for all approved ids, tenant-scoped
        model.update_many.assert_awaited_once()
        call = model.update_many.await_args.kwargs
        assert call["where"] == {"id": {"in": ["a", "b", "c"]}, "tenant_id": "t1"}
        assert call["data"]["control_status"] == "approved"

    @pytest.mark.asyncio
    async def test_flagged_and_blocked_written_individually_with_reason(self):
        from app.tools.spend_control import _persist_control_status
        model = self._model()
        await _persist_control_status(model, "t1", [
            ("a", "approved", "ok"),
            ("b", "flagged", "possible duplicate"),
            ("c", "blocked", "over limit"),
        ])
        # 1 batched approved + 1 per flagged + 1 per blocked = 3 calls
        assert model.update_many.await_count == 3
        wheres = [c.kwargs["where"] for c in model.update_many.await_args_list]
        # every write is tenant-scoped
        assert all(w.get("tenant_id") == "t1" for w in wheres)
        by_id = {
            c.kwargs["where"]["id"]: c.kwargs["data"]
            for c in model.update_many.await_args_list
            if c.kwargs["where"]["id"] in ("b", "c")
        }
        assert by_id["b"]["control_status"] == "flagged"
        assert by_id["b"]["control_reason"] == "possible duplicate"
        assert by_id["c"]["control_status"] == "blocked"

    @pytest.mark.asyncio
    async def test_no_approved_ids_skips_batch_update(self):
        from app.tools.spend_control import _persist_control_status
        model = self._model()
        await _persist_control_status(model, "t1", [("c", "blocked", "over limit")])
        # only the individual blocked write, no empty approved batch
        assert model.update_many.await_count == 1
        assert model.update_many.await_args.kwargs["where"]["id"] == "c"

    @pytest.mark.asyncio
    async def test_reason_truncated_to_500_chars(self):
        from app.tools.spend_control import _persist_control_status
        model = self._model()
        await _persist_control_status(model, "t1", [("b", "flagged", "x" * 900)])
        assert len(model.update_many.await_args.kwargs["data"]["control_reason"]) == 500
