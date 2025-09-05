import pytest
from app.config import settings
from pytest import approx

class TestBillingCalculations:
    def test_vcpu_billing_calculation(self):
        cores, cpu_percent, hours = 2, 50, 1
        vcpu_hours = (cpu_percent / 100.0) * cores * hours
        assert vcpu_hours == 1.0
        assert vcpu_hours * settings.vcpu_rate_per_core_hour == approx(0.01)

    def test_ram_billing_calculation(self):
        ram_hours = 4 * 2
        assert ram_hours == 8.0
        assert ram_hours * settings.ram_rate_per_gib_hour == approx(0.012)

    def test_disk_billing_calculation(self):
        disk_hours = 100 * 24
        assert disk_hours == 2400.0
        assert disk_hours * settings.disk_rate_per_gib_hour == approx(0.12)

    def test_complex_billing_scenario(self):
        vcpu_hours = (0.75 * 4) * 12
        vcpu_cost = vcpu_hours * settings.vcpu_rate_per_core_hour
        ram_hours = 8 * 12
        ram_cost = ram_hours * settings.ram_rate_per_gib_hour
        disk_hours = 50 * 12
        disk_cost = disk_hours * settings.disk_rate_per_gib_hour
        total_cost = vcpu_cost + ram_cost + disk_cost

        assert vcpu_hours == 36.0
        assert vcpu_cost == approx(0.36)
        assert ram_hours == 96.0
        assert ram_cost == approx(0.144)
        assert disk_hours == 600.0
        assert disk_cost == approx(0.03)
