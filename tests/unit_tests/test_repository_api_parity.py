import inspect

from repom.repositories import AsyncBaseRepository, BaseRepository


# Add a method name here only when its public API intentionally differs.
INTENTIONAL_API_DIFFERENCES: set[str] = set()
ASYNC_SYNC_HELPERS = {"parse_order_by", "set_find_option"}


def _public_callables(repository_class):
    return {
        name: member
        for name, member in inspect.getmembers(repository_class, predicate=callable)
        if not name.startswith("_")
    }


def _parameter_list(method):
    return [
        (parameter.name, parameter.kind, parameter.default)
        for parameter in inspect.signature(method).parameters.values()
    ]


def test_sync_and_async_repository_public_apis_match():
    sync_methods = _public_callables(BaseRepository)
    async_methods = _public_callables(AsyncBaseRepository)

    differences = set(sync_methods) ^ set(async_methods)
    differences.update(
        name
        for name in sync_methods.keys() & async_methods.keys()
        if _parameter_list(sync_methods[name]) != _parameter_list(async_methods[name])
    )

    assert differences == INTENTIONAL_API_DIFFERENCES


def test_async_repository_io_methods_are_coroutines():
    async_methods = _public_callables(AsyncBaseRepository)

    assert ASYNC_SYNC_HELPERS <= async_methods.keys()
    for name, method in async_methods.items():
        if name in ASYNC_SYNC_HELPERS:
            assert not inspect.iscoroutinefunction(method)
        else:
            assert inspect.iscoroutinefunction(method)
