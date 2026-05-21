"""
Functional index on LOWER(auth_user.email) so case-insensitive email lookups
(used on every login and registration) are O(log n) instead of a full scan.

CREATE INDEX CONCURRENTLY runs without taking an ACCESS EXCLUSIVE lock,
so it is safe to run against a live production database. It cannot run
inside a transaction, hence atomic = False.

SQLite does not support CONCURRENTLY or functional indexes the same way —
the RunSQL operations are skipped automatically when using SQLite (local dev).
"""
from django.db import migrations, connection


def create_index(apps, schema_editor):
    if connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "auth_user_email_lower_idx ON auth_user (LOWER(email));"
        )
    # SQLite: skip — not needed for local dev


def drop_index(apps, schema_editor):
    if connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS auth_user_email_lower_idx;"
        )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_index, reverse_code=drop_index),
    ]