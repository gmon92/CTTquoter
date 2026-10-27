"""Identity boundary shared by HTTP clients and quote storage.

A future account provider resolves this context after authentication. Clients
never choose ownership IDs in a quote payload or URL. The existing login maps
to one shared team profile until individual employee accounts are configured.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AccountContext:
    account_id: str
    profile_id: str
    workspace_id: str
    display_name: str
    shared: bool = False

    def public_profile(self):
        return {"id": self.profile_id, "display_name": self.display_name, "shared": self.shared}


SHARED_TEAM = AccountContext('shared-team', 'shared-team', 'default', 'Shared team', True)
