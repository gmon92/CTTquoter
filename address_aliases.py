"""Explicit location shorthand for routing and displayed quote addresses."""

AIRPORT_ADDRESSES = {
    'CHO': 'Charlottesville Albemarle Airport (CHO), 100 Bowen Loop, Charlottesville, VA 22911',
    'IAD': 'Washington Dulles International Airport (IAD), 1 Saarinen Circle, Dulles, VA 20166',
    'RIC': 'Richmond International Airport (RIC), 1 Richard E Byrd Terminal Drive, Richmond, VA 23250',
    'DCA': 'Ronald Reagan Washington National Airport (DCA), 2401 Smith Boulevard, Arlington, VA 22202',
    'BWI': 'Baltimore Washington International Airport (BWI), 7050 Friendship Road, Baltimore, MD 21240',
    'ROA': 'Roanoke Blacksburg Regional Airport (ROA), 5202 Aviation Drive NW, Roanoke, VA 24012',
    'LYH': 'Lynchburg Regional Airport (LYH), 350 Terminal Drive, Lynchburg, VA 24502',
}


LOCATION_ADDRESSES = {
    'BHI': "Boar's Head Resort, 200 Ednam Drive, Charlottesville, VA 22903",
    'KESWICK': 'Keswick Hall, 701 Club Drive, Keswick, VA 22947',
    'FARMINGTON': 'Farmington Country Club, 1625 Country Club Circle, Charlottesville, VA 22901',
}


def resolve_address(address):
    """Expand exact location shortcuts; leave street addresses and unknown names intact."""
    address = address.strip()
    shorthand = ' '.join(address.upper().split())
    if shorthand in LOCATION_ADDRESSES:
        return LOCATION_ADDRESSES[shorthand]
    if shorthand.endswith(' AIRPORT'):
        shorthand = shorthand[:-8]
    return AIRPORT_ADDRESSES.get(shorthand, address)
