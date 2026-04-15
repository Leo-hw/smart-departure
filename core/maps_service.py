"""Travel-time provider selection and lookup stubs."""


class _BaseProvider:
    def calculate(self, origin, destination):
        raise NotImplementedError


class _GoogleMapsProvider(_BaseProvider):
    def calculate(self, origin, destination):
        raise NotImplementedError("Google Maps travel time lookup is not implemented yet.")


class _KakaoMapsProvider(_BaseProvider):
    def calculate(self, origin, destination):
        raise NotImplementedError("Kakao Maps travel time lookup is not implemented yet.")


def _select_provider(transport_mode):
    if transport_mode == "driving":
        return _KakaoMapsProvider()
    return _GoogleMapsProvider()


def get_travel_time(origin, destination, transport_mode):
    """Return travel time in minutes for the given transport mode."""
    provider = _select_provider(transport_mode)
    return provider.calculate(origin, destination)
