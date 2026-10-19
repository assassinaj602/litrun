from litrun.governor import poll_governor, check_ram_envelope, GovernorStatus


def test_poll_governor():
    gov = poll_governor()
    assert isinstance(gov, GovernorStatus)
    assert gov.ram_total_mb > 0
    assert gov.online_cores > 0
    assert gov.recommended_threads > 0
    assert gov.thermal_state in ["nominal", "warm", "critical"]


def test_check_ram_envelope_safe():
    allowed, needed, reason, tight = check_ram_envelope(
        model_size_mb=397,
        context_length=2048,
        kv_bytes_per_token=32.0,
    )
    assert needed > 397
    assert len(reason) > 0


def test_check_ram_envelope_blocked_huge():
    allowed, needed, reason, tight = check_ram_envelope(
        model_size_mb=10_000_000,
        context_length=8192,
    )
    assert not allowed
    assert tight
    assert "OOM RISK" in reason
