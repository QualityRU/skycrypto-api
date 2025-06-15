from typing import Type, TypeVar, Any

T = TypeVar("T")


def mapping_result_to_dict(keys: list, values: Any) -> dict:
    return dict(zip(keys, values))


def mapping_result_to_dto(result: Any, dto: Type[T]) -> T:
    result_first = result.first()
    result_keys = result.keys()
    return dto(**mapping_result_to_dict(result_keys, result_first)) if result_first is not None else result_first
