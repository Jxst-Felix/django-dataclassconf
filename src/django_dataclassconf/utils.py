from dataclasses import fields, is_dataclass


def _to_config_data(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_config_data(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, dict):
        return {
            key: _to_config_data(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _to_config_data(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _to_config_data(item)
            for item in value
        )
    return value
