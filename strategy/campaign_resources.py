"""Auditable resource-only retries keep the frozen strategic study unchanged."""
from strategy.state_contract import StrategyError,digest

ALLOWED={'memory_mb','work_disk_mb','timeout_seconds'}


def resource_profile(plan,overrides,reason):
    value=dict(schema='software.hu-campaign-resource-profile.v1',campaign_plan_sha256=plan['plan_sha256'],
        overrides=dict(overrides),reason=str(reason))
    value['profile_sha256']=digest(value)
    checked_resource_profile(value,plan)
    return value


def checked_resource_profile(value,plan):
    body=dict(value);claimed=body.pop('profile_sha256',None)
    if (value.get('schema')!='software.hu-campaign-resource-profile.v1' or digest(body)!=claimed
            or value.get('campaign_plan_sha256')!=plan['plan_sha256']):
        raise StrategyError('RESOURCE_PROFILE_HASH_OR_CAMPAIGN_MISMATCH')
    overrides=value.get('overrides',{})
    if (not overrides or set(overrides)-ALLOWED
            or any(type(v) is not int or v<plan['settings'][k] for k,v in overrides.items())):
        raise StrategyError('ONLY_INCREASED_RESOURCE_BUDGETS_ALLOWED_NO_STRATEGY_OVERRIDES')
    return value


def effective_settings(plan,profile=None):
    settings=dict(plan['settings'])
    if profile:settings.update(checked_resource_profile(profile,plan)['overrides'])
    return settings
