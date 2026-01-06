import json
import pytest

# Import the module under test (script is importable)
import swap_cronos_tokens as s

# Sample token addresses (same as in the script)
USDC = "0xc21223249CA28397B4B6541dfFaEcC539BfF0c59"
DAI = "0xF2001B145b43032AAF5Ee2884e456CCd805F677D"


class FakeReceipt:
    def __init__(self):
        self.status = 1
        self.gasUsed = 123456
        self.blockNumber = 999999


class FakeSwapFn:
    def estimate_gas(self, kwargs):
        return 120000

    def build_transaction(self, kwargs):
        # Return a minimal tx dict that signing code expects
        return {"gas": kwargs.get("gas", 120000), "nonce": kwargs.get("nonce", 0)}


class FakeFunctionCall:
    def __init__(self, ret):
        self._ret = ret

    def call(self):
        return self._ret


class FakeContract:
    def __init__(self, expected_out):
        self._expected_out = expected_out

    @property
    def functions(self):
        # Provide the functions used: getAmountsOut and swap* functions
        class F:
            def __init__(self, expected_out):
                self._expected_out = expected_out

            def getAmountsOut(self, amount_in, path):
                # Return [amount_in, expected_out] (mimic getAmountsOut)
                return FakeFunctionCall([amount_in, self._expected_out])

            def swapExactETHForTokens(self, *args, **kwargs):
                return FakeSwapFn()

            def swapExactTokensForETH(self, *args, **kwargs):
                return FakeSwapFn()

            def swapExactTokensForTokens(self, *args, **kwargs):
                return FakeSwapFn()

        return F(self._expected_out)


class FakeEth:
    def __init__(self, expected_out, account_address="0xFAKE"):
        self._contract_expected_out = expected_out
        self.account = self  # minimal account with from_key
        self._nonce = 0

    def from_key(self, _):
        class A:
            address = "0xFAKE"
        return A()

    def sign_transaction(self, tx, private_key):
        # Minimal signed tx object with raw transaction bytes
        class Signed:
            raw_transaction = b"\x01" * 32
        return Signed()

    def contract(self, address=None, abi=None):
        return FakeContract(self._contract_expected_out)

    @property
    def gas_price(self):
        return 1

    @property
    def chain_id(self):
        return 25

    def get_transaction_count(self, addr):
        self._nonce += 1
        return self._nonce

    def send_raw_transaction(self, raw):
        # Return fake tx hash bytes
        return b"\xab" * 32

    def wait_for_transaction_receipt(self, tx_hash, timeout=120):
        return FakeReceipt()

    def get_balance(self, addr):
        return 10 ** 18  # ample native balance


class FakeW3:
    def __init__(self, expected_out):
        self.eth = FakeEth(expected_out)


def test_simulate_erc20_to_erc20(monkeypatch):
    # Avoid approval RPC in simulation
    monkeypatch.setattr(s, "ensure_token_approval", lambda *args, **kwargs: True)
    w3 = FakeW3(expected_out=49904252691053346)
    result = s.execute_vvs_swap(
        w3=w3,
        from_amount_wei=50000,
        from_token=USDC,
        to_token=DAI,
        private_key="0xdeadbeef",
        slippage_pct=1.0,
        simulate=True,
    )
    assert isinstance(result, dict)
    assert result["status"] == "simulated"
    assert result["amountIn"] == "50000"
    assert "expectedOut" in result
    assert result["path"] == [USDC, DAI]


def test_execute_erc20_to_erc20_success(monkeypatch):
    # Use a FakeW3 which will "succeed" sending tx + receipt
    w3 = FakeW3(expected_out=49904252691053346)

    # Avoid performing approval on-chain; ensure_token_approval returns True
    monkeypatch.setattr(s, "ensure_token_approval", lambda *args, **kwargs: True)

    result = s.execute_vvs_swap(
        w3=w3,
        from_amount_wei=50000,
        from_token=USDC,
        to_token=DAI,
        private_key="0xdeadbeef",
        slippage_pct=1.0,
        simulate=False,
    )

    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert "txHash" in result
    assert result["amountIn"] == "50000"
    assert int(result["expectedOut"]) == 49904252691053346
    assert result["gasUsed"] == 123456


# Run with: pytest -q tests/test_swap_vvs.py
