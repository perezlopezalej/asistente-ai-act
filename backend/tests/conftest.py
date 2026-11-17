"""Los tests que no son de integración no dependen del .env ni del entorno local.

Se sustituye `settings` por una configuración sin credenciales y con los valores por
defecto (sin leer .env), de modo que en local se comporten igual que en el CI. Los
`test_integracion_*` siguen usando la configuración real (.env).
"""

import pytest

from app.config import Settings, settings


@pytest.fixture(autouse=True)
def configuracion_aislada(request, monkeypatch):
    if request.module.__name__.rsplit(".", 1)[-1].startswith("test_integracion_"):
        return
    limpia = Settings(_env_file=None)
    for nombre in Settings.model_fields:
        monkeypatch.setattr(settings, nombre, getattr(limpia, nombre))
