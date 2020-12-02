import os
from functools import lru_cache
from typing import cast

import requests

from ..constants import VerifiedResult
from ..core.plugins import Plugin
from ..settings import get_settings
from ..types import SelfAwareCallable
from ..util.code_snippet import CodeSnippet
from ..util.inject import get_injectable_variables
from ..util.inject import inject_variables_into_function
from .util import get_caller_path


def is_invalid_file(filename: str) -> bool:
    return not os.path.isfile(filename)


def is_baseline_file(filename: str) -> bool:
    return filename == _get_baseline_filename()


@lru_cache(maxsize=1)
def _get_baseline_filename() -> str:
    path = get_caller_path(offset=1)
    return cast(str, get_settings().filters[path]['filename'])


def is_ignored_due_to_verification_policies(
    secret: str,
    plugin: Plugin,
    context: CodeSnippet,
) -> bool:
    """
    Valid policies include:
        - Only VERIFIED_TRUE
        - Can be UNVERIFIED or VERIFIED_TRUE
        - Disabled check.

    There's no such thing as "only verified false", because if you're going to verify
    something, and it's verified false, why are you still including it as a valid secret?
    """
    function = plugin.__class__.verify
    if not hasattr(function, 'injectable_variables'):
        function.injectable_variables = set(get_injectable_variables(plugin.verify))  # type: ignore
        function.path = f'{plugin.__class__.__name__}.verify'   # type: ignore

    try:
        verify_result = inject_variables_into_function(
            cast(SelfAwareCallable, function),
            self=plugin,
            secret=secret,
            context=context,
        )
    except requests.exceptions.RequestException:
        verify_result = VerifiedResult.UNVERIFIED

    if not verify_result:
        return False

    if verify_result.value < _get_verification_policy().value:
        return True

    return False


@lru_cache(maxsize=1)
def _get_verification_policy() -> VerifiedResult:
    path = get_caller_path(offset=1)
    return VerifiedResult(get_settings().filters[path]['min_level'])
