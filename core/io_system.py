"""Input abstraction layer for keyboard and mouse."""


class InputSystem:
    def poll(self) -> None:
        """Poll current input state."""
        return None

