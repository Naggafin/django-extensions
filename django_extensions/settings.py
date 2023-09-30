# -*- coding: utf-8 -*-
import os

from django.conf import settings

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
REPLACEMENTS = getattr(settings, 'EXTENSIONS_REPLACEMENTS', {})

DEFAULT_SQLITE_ENGINES = (
    'django.db.backends.sqlite3',
    'django.db.backends.spatialite',
)
DEFAULT_MYSQL_ENGINES = (
    'django.db.backends.mysql',
    'django.contrib.gis.db.backends.mysql',
    'mysql.connector.django',
)
DEFAULT_POSTGRESQL_ENGINES = (
    'django.db.backends.postgresql',
    'django.db.backends.postgresql_psycopg2',
    'django.db.backends.postgis',
    'django.contrib.gis.db.backends.postgis',
    'psqlextra.backend',
    'django_zero_downtime_migrations.backends.postgres',
    'django_zero_downtime_migrations.backends.postgis',
)

SQLITE_ENGINES = getattr(settings, 'DJANGO_EXTENSIONS_RESET_DB_SQLITE_ENGINES', DEFAULT_SQLITE_ENGINES)
MYSQL_ENGINES = getattr(settings, 'DJANGO_EXTENSIONS_RESET_DB_MYSQL_ENGINES', DEFAULT_MYSQL_ENGINES)
POSTGRESQL_ENGINES = getattr(settings, 'DJANGO_EXTENSIONS_RESET_DB_POSTGRESQL_ENGINES', DEFAULT_POSTGRESQL_ENGINES)

DEFAULT_PRINT_SQL_TRUNCATE_CHARS = 1000

SELECT_ACTION_TEMPLATE = getattr(settings, 'DJANGO_EXTENSIONS_SELECT_ACTION_TEMPLATE', "django_extensions/select_actions_form.html")
LIST_FILTER_TEMPLATE = getattr(settings, 'DJANGO_EXTENSIONS_LIST_FILTER_TEMPLATE', "admin/filter.html")
LIST_FILTERS_TEMPLATE = getattr(settings, 'DJANGO_EXTENSIONS_LIST_FILTERS_TEMPLATE', "django_extensions/list_filters.html")
ADJUSTABLE_PAGINATION_TEMPLATE = getattr(
	settings, 'DJANGO_EXTENSIONS_ADJUSTABLE_PAGINATION_TEMPLATE', "django_extensions/adjustable_pagination_form.html"
)
