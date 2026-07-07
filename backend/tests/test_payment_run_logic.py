"""
Unit tests for payment_run bill-classification and threshold/policy logic.
Pure-function tests — no DB, Claude, or network. Covers _parse_policy and
_classify_bills, including threshold boundaries and the due-window filter.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.tools.payment_run import _ToolPolicy, _classify_bills, _parse_policy


def _bill(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="bill_1",
        contact_name="Acme Ltd",
        total_cents=50_000,
        outstanding_cents=50_000,
        due_date=date(2026, 7, 8),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


DEFAULT_POLICY = _ToolPolicy()  # auto=100_000, approval=250_000, window=7, max=50
TODAY = date(2026, 7, 7)


class TestParsePolicy:
    def test_defaults_when_empty(self):
        p = _parse_policy({})
        assert p.auto_pay_limit_cents == 100_000
        assert p.approval_threshold_cents == 250_000
        assert p.due_within_days == 7
        assert p.max_bills_per_run == 50

    def test_reads_flat_config(self):
        p = _parse_policy({
            "auto_pay_limit_cents": 20_000,
            "approval_threshold_cents": 500_000,
            "due_within_days": 14,
            "max_bills_per_run": 10,
        })
        assert p.auto_pay_limit_cents == 20_000
        assert p.approval_threshold_cents == 500_000
        assert p.due_within_days == 14
        assert p.max_bills_per_run == 10

    def test_reads_nested_policy_key(self):
        p = _parse_policy({"policy": {"auto_pay_limit_cents": 33_000}})
        assert p.auto_pay_limit_cents == 33_000
        # unspecified fields fall back to defaults
        assert p.approval_threshold_cents == 250_000

    def test_partial_config_keeps_defaults(self):
        p = _parse_policy({"due_within_days": 3})
        assert p.due_within_days == 3
        assert p.auto_pay_limit_cents == 100_000


class TestClassifyBills:
    def test_schedule_when_within_auto_pay_limit(self):
        [s] = _classify_bills([_bill(outstanding_cents=50_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "schedule_payment"
        assert s.reason == "within_auto_pay_limit"

    def test_approval_when_between_auto_and_approval(self):
        [s] = _classify_bills([_bill(outstanding_cents=150_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "request_approval"
        assert s.reason == "between_auto_and_approval_threshold"

    def test_approval_when_exceeds_approval_threshold(self):
        [s] = _classify_bills([_bill(outstanding_cents=300_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "request_approval"
        assert s.reason.startswith("exceeds_approval_threshold")

    def test_boundary_exactly_at_auto_pay_limit_schedules(self):
        # outstanding == auto_pay_limit → schedule (<= is inclusive)
        [s] = _classify_bills([_bill(outstanding_cents=100_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "schedule_payment"

    def test_boundary_exactly_at_approval_threshold_requires_approval(self):
        # outstanding == approval_threshold → not > threshold, not <= auto limit → approval
        [s] = _classify_bills([_bill(outstanding_cents=250_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "request_approval"
        assert s.reason == "between_auto_and_approval_threshold"

    def test_skip_when_due_beyond_window(self):
        far = TODAY + timedelta(days=30)
        [s] = _classify_bills([_bill(due_date=far, outstanding_cents=10_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "skip"
        assert s.reason == "not_due_within_window"

    def test_skip_when_due_date_missing(self):
        [s] = _classify_bills([_bill(due_date=None, outstanding_cents=10_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "skip"
        assert s.due_date is None

    def test_overdue_bill_is_still_scheduled(self):
        past = TODAY - timedelta(days=5)
        [s] = _classify_bills([_bill(due_date=past, outstanding_cents=10_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "schedule_payment"

    def test_due_exactly_on_cutoff_is_in_window(self):
        cutoff = TODAY + timedelta(days=DEFAULT_POLICY.due_within_days)  # not > cutoff
        [s] = _classify_bills([_bill(due_date=cutoff, outstanding_cents=10_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "schedule_payment"

    def test_datetime_due_date_is_normalised_to_date(self):
        dt = datetime(2026, 7, 8, 15, 30, 0)
        [s] = _classify_bills([_bill(due_date=dt, outstanding_cents=10_000)], DEFAULT_POLICY, TODAY)
        assert s.action == "schedule_payment"
        assert s.due_date == "2026-07-08"

    def test_respects_max_bills_per_run_cap(self):
        policy = _ToolPolicy(max_bills_per_run=2)
        bills = [_bill(id=f"b{i}", outstanding_cents=10_000) for i in range(5)]
        result = _classify_bills(bills, policy, TODAY)
        assert len(result) == 2

    def test_currency_is_integer_minor_units_passthrough(self):
        # amounts are carried through as integer cents — never floats
        [s] = _classify_bills([_bill(outstanding_cents=12_345, total_cents=12_345)], DEFAULT_POLICY, TODAY)
        assert isinstance(s.outstanding_cents, int)
        assert s.outstanding_cents == 12_345

    def test_mixed_batch_partitions_correctly(self):
        bills = [
            _bill(id="auto", outstanding_cents=40_000),           # schedule
            _bill(id="mid", outstanding_cents=180_000),           # approval (between)
            _bill(id="big", outstanding_cents=400_000),           # approval (exceeds)
            _bill(id="late", due_date=TODAY + timedelta(days=90), outstanding_cents=5_000),  # skip
        ]
        result = _classify_bills(bills, DEFAULT_POLICY, TODAY)
        by_id = {s.id: s.action for s in result}
        assert by_id == {
            "auto": "schedule_payment",
            "mid": "request_approval",
            "big": "request_approval",
            "late": "skip",
        }
