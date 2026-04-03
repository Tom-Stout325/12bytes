import os

env_name = os.getenv("ENV_NAME", "local").lower()

if env_name == "prod":
    from .settings_prod import *  # noqa
else:
    from .settings_local import *  # noqa
