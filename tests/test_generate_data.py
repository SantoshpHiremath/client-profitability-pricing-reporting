from src.generate_data import generate_dataset


class TestDeterminism:
    def test_same_seed_produces_identical_dataset(self):
        d1 = generate_dataset(seed=42)
        d2 = generate_dataset(seed=42)
        assert [c.contract_id for c in d1.contracts] == [c.contract_id for c in d2.contracts]
        assert [i.amount for i in d1.invoices] == [i.amount for i in d2.invoices]

    def test_different_seed_produces_different_dataset(self):
        d1 = generate_dataset(seed=42)
        d2 = generate_dataset(seed=7)
        assert [c.monthly_rate for c in d1.contracts] != [c.monthly_rate for c in d2.contracts]


class TestReferentialIntegrity:
    def test_every_invoice_contract_id_exists_except_the_deliberate_orphan(self):
        dataset = generate_dataset(seed=42)
        contract_ids = {c.contract_id for c in dataset.contracts}
        missing = [inv for inv in dataset.invoices if inv.contract_id not in contract_ids]
        assert len(missing) == 1
        assert missing[0].contract_id == "CTR-9999"

    def test_every_pricing_measure_affected_contract_id_exists(self):
        dataset = generate_dataset(seed=42)
        contract_ids = {c.contract_id for c in dataset.contracts}
        for pm in dataset.pricing_measures:
            for cid in pm.affected_contract_ids:
                assert cid in contract_ids


class TestShape:
    def test_expected_counts(self):
        dataset = generate_dataset(seed=42)
        assert len(dataset.contracts) == 40
        assert len(dataset.customers) == 12
        assert len(dataset.products) == 6
        assert len(dataset.pricing_measures) == 4
