class TransientProviderError(Exception):
    """Provider guarantees NOTHING was sent -> safe to retry."""


class PermanentProviderError(Exception): ...


class MockEmailProvider:
    def send(self, to: str, subject: str, body: str, idempotency_key: str) -> str:
        if "+fail" in to:
            raise PermanentProviderError("Mailbox rejected (simulated)")
        return f"mock-{idempotency_key[:16]}"


def get_email_provider(db, org_id):
    # Later: look up the org's connected email Integration and return SES/SendGrid/Gmail adapters.
    return MockEmailProvider()
